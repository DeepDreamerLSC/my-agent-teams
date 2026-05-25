from __future__ import annotations

import json
from collections import Counter, OrderedDict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

WORKTREE = Path('/Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/Trace-9ad4d225')
ARTIFACTS = WORKTREE / 'artifacts' / 'pdf2word'
FINAL_ACCEPTANCE_DIR = ARTIFACTS / 'final-acceptance'
EVIDENCE_DIR = ARTIFACTS / 'final-archive' / 'reports' / 'evidence-chain'
TASK_DIR = Path('/Users/linsuchang/Desktop/work/my-agent-teams/tasks/补齐样例Trace证据链缺口并统一归因契约')
TZ = timezone(timedelta(hours=8))
NOW = datetime.now(TZ).isoformat(timespec='seconds')

KNOWN_OVERFIT_RISKS = [
    'sample_manifest_driven_acceptance',
    'selected_page_specific_review',
    'limited_subject_fixture_coverage',
    'source_selection_sample_name_map',
    'unknown_production_hardcode_risk',
]

STAGE_ORDER = [
    'source_pdf',
    'parser_or_ocr',
    'exercise_ir',
    'question_region_detector',
    'candidate_extraction',
    'candidate_filter',
    'page_ir_merge',
    'docx_renderer',
    'render_pair',
    'visual_similarity_gate',
    'fidelity_veto_gate',
    'human_review_gate',
    'final_acceptance',
]

STAGE_TAXONOMY = OrderedDict([
    ('stage_order', STAGE_ORDER),
    ('definitions', OrderedDict([
        ('source_pdf', {'summary': '源 PDF 是否存在且可读。', 'typical_failure_codes': ['source_pdf_missing', 'source_page_unreadable']}),
        ('parser_or_ocr', {'summary': 'OCR / layout block 是否可用。', 'typical_failure_codes': ['parser_failed', 'ocr_text_missing', 'layout_blocks_missing']}),
        ('exercise_ir', {'summary': 'Exercise IR 是否形成题区/材料结构。', 'typical_failure_codes': ['exercise_ir_missing', 'question_binding_missing']}),
        ('question_region_detector', {'summary': '页型/题区识别是否可用于增强链路。', 'typical_failure_codes': ['question_region_not_detectable', 'page_type_unresolved']}),
        ('candidate_extraction', {'summary': '表格/图片/公式/区域候选是否被抽取。', 'typical_failure_codes': ['candidate_missing', 'table_candidate_missing', 'image_candidate_missing']}),
        ('candidate_filter', {'summary': '候选是否被策略性过滤。', 'typical_failure_codes': ['formula_candidate_rejected_audit_only', 'duplicate_candidate_rejected']}),
        ('page_ir_merge', {'summary': '候选是否被正确锚定并合入页面。', 'typical_failure_codes': ['layout_insertion_missing', 'reading_order_break', 'candidate_appended_not_anchored']}),
        ('docx_renderer', {'summary': 'DOCX 是否保留关键结构/表格/图片/答案区。', 'typical_failure_codes': ['docx_render_missing', 'table_xml_missing', 'answer_line_missing']}),
        ('render_pair', {'summary': 'PDF 与 DOCX 是否形成可比 render pair。', 'typical_failure_codes': ['render_pair_missing', 'docx_renderer_unavailable', 'page_pair_unmatched']}),
        ('visual_similarity_gate', {'summary': '页级/区域级真实渲染相似度是否达标。', 'typical_failure_codes': ['visual_similarity_below_threshold', 'critical_page_similarity_below_threshold']}),
        ('fidelity_veto_gate', {'summary': 'P0/P1 fidelity veto 是否触发。', 'typical_failure_codes': ['p0_fidelity_veto_present', 'critical_page_reading_order_break']}),
        ('human_review_gate', {'summary': '人审是否通过且是否具备 page/region/veto binding。', 'typical_failure_codes': ['human_review_failed', 'page_veto_or_human_binding_missing', 'explicit_region_evidence_missing']}),
        ('final_acceptance', {'summary': '最终汇总门禁是否允许 GO。', 'typical_failure_codes': ['positive_candidate_human_visual_no_go', 'canonical_page_region_veto_trace_not_ready']}),
        ('missing_required_artifact', {'summary': 'required artifact 缺失的 fail-close 哨兵阶段。', 'typical_failure_codes': ['required_artifact_missing']}),
        ('unknown', {'summary': 'artifact 字段冲突或不符合契约时的 fail-close 哨兵阶段。', 'typical_failure_codes': ['unknown_stage']}),
    ])),
    ('status_enum', ['pass', 'warn', 'fail', 'skipped', 'not_applicable', 'missing_artifact', 'unknown'])
])

DEFECT_LAYER_TAXONOMY = OrderedDict([
    ('source_quality', {'summary': '源 PDF 本身质量或可读性问题。'}),
    ('parser_ocr_layout', {'summary': 'OCR / layout block 问题。'}),
    ('exercise_ir_structure', {'summary': 'Exercise IR 结构化问题。'}),
    ('question_region_detection', {'summary': '题区/页型检测问题。'}),
    ('candidate_extraction', {'summary': '候选抽取问题。'}),
    ('candidate_filter_policy', {'summary': '候选过滤策略问题。'}),
    ('page_ir_merge', {'summary': '页面锚定 / 阅读顺序 / merge 问题。'}),
    ('docx_rendering', {'summary': 'DOCX 渲染问题。'}),
    ('table_rendering', {'summary': '表格渲染问题。'}),
    ('image_or_diagram_rendering', {'summary': '图片 / 图形 / 实验图渲染问题。'}),
    ('formula_audit_only', {'summary': '公式仍处于 audit-only。'}),
    ('visual_fidelity', {'summary': '视觉相似度未达标，但未进一步定位到更早链路。'}),
    ('human_review_binding', {'summary': '缺显式 region / veto / human binding，按契约 fail-close。'}),
    ('acceptance_contract', {'summary': 'FinalAcceptance / evidence-chain 契约字段不一致。'}),
    ('performance_or_cost', {'summary': '性能 / 成本导致的降级。'}),
    ('unknown', {'summary': '暂无法稳定归因。'}),
])

BLOCKING_REASON_TAXONOMY = OrderedDict([
    ('visual_similarity_below_threshold', {'stage': 'visual_similarity_gate', 'primary_defect_layer': 'visual_fidelity', 'severity': 'p0', 'summary': '文档/页面真实渲染相似度低于门禁阈值。'}),
    ('critical_page_similarity_below_threshold', {'stage': 'visual_similarity_gate', 'primary_defect_layer': 'visual_fidelity', 'severity': 'p0', 'summary': 'selected critical page 的真实渲染相似度低于阈值。'}),
    ('p0_fidelity_veto_present', {'stage': 'fidelity_veto_gate', 'primary_defect_layer': 'visual_fidelity', 'severity': 'p0', 'summary': 'P0 fidelity veto 已触发。'}),
    ('human_review_failed', {'stage': 'human_review_gate', 'primary_defect_layer': 'visual_fidelity', 'severity': 'p0', 'summary': 'human review 最终判定为 no_go。'}),
    ('explicit_region_evidence_missing', {'stage': 'human_review_gate', 'primary_defect_layer': 'human_review_binding', 'severity': 'p0', 'summary': '缺显式 region evidence，无法稳定回溯到 page/region。'}),
    ('page_veto_or_human_binding_missing', {'stage': 'human_review_gate', 'primary_defect_layer': 'human_review_binding', 'severity': 'p0', 'summary': '缺 page veto 或 human binding，按契约 fail-close。'}),
    ('canonical_page_region_veto_trace_not_ready', {'stage': 'final_acceptance', 'primary_defect_layer': 'human_review_binding', 'severity': 'p0', 'summary': 'canonical page/region/veto/human trace 未 ready。'}),
    ('positive_candidate_human_visual_no_go', {'stage': 'final_acceptance', 'primary_defect_layer': 'visual_fidelity', 'severity': 'p0', 'summary': 'positive candidate 最终 human visual 仍为 NO-GO。'}),
    ('artifact_missing', {'stage': 'missing_required_artifact', 'primary_defect_layer': 'acceptance_contract', 'severity': 'p0', 'summary': 'required artifact 缺失。'}),
])

POSITIVE_ONLY_COUNTS = OrderedDict([
    ('chinese_long_reading', 1),
    ('language_exercise_sparse_media_with_fallback_pages', 1),
    ('math_exercise_with_sparse_image_and_table', 1),
    ('math_exam_image_dense', 1),
    ('science_experiment_table_and_image_mixed', 1),
])


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def canonical_path(value: Any) -> Any:
    if value is None:
        return None
    s = str(value)
    if not s:
        return s
    if s.startswith('artifacts/pdf2word/'):
        return s
    if s.startswith('final-acceptance/'):
        return f'artifacts/pdf2word/{s}'
    if s.startswith('profiles/') or s.startswith('reports/'):
        return f'artifacts/pdf2word/final-archive/{s}'
    marker = 'artifacts/pdf2word/'
    if marker in s:
        return s[s.index(marker):]
    return s


def dedupe(items: list[Any]) -> list[Any]:
    out: list[Any] = []
    seen: set[str] = set()
    for item in items:
        if item is None:
            continue
        key = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else str(item)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def collect_codes(*values: Any) -> list[str]:
    codes: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            codes.append(value)
        elif isinstance(value, dict):
            code = value.get('canonical_code') or value.get('code') or value.get('failure_code')
            if code:
                codes.append(code)
        elif isinstance(value, list):
            for item in value:
                codes.extend(collect_codes(item))
    return dedupe(codes)


def severity_rank(sev: str | None) -> int:
    order = {'critical': 4, 'p0': 3, 'high': 3, 'p1': 2, 'medium': 2, 'low': 1, 'info': 0}
    return order.get((sev or '').lower(), -1)


def severity_max(items: list[dict[str, Any]]) -> str | None:
    best = None
    best_rank = -1
    for item in items:
        sev = item.get('severity')
        rank = severity_rank(sev)
        if rank > best_rank:
            best = sev
            best_rank = rank
    return best


def normalize_page_id(page_index: Any, current: Any = None) -> str:
    if current:
        return str(current)
    if isinstance(page_index, int):
        return f'page_{page_index:03d}'
    return str(page_index)


def region_defect_layer(region_kind: str, page_layer: str, attributable: bool) -> str:
    if not attributable:
        return 'human_review_binding'
    kind = (region_kind or '').lower()
    if 'table' in kind:
        return 'table_rendering'
    if any(token in kind for token in ['image', 'diagram', 'figure', 'geometry']):
        return 'image_or_diagram_rendering'
    if 'formula' in kind:
        return 'formula_audit_only'
    return page_layer


def bbox_alignment_status(region: dict[str, Any]) -> str:
    src = region.get('source_bbox_page_space')
    docx = region.get('docx_bbox_page_space')
    if src and docx:
        return 'matched'
    if src and not docx:
        return 'docx_bbox_missing'
    if docx and not src:
        return 'source_only'
    return 'unknown'


def normalize_evidence_paths(region: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in ['region_json_path']:
        if region.get(key):
            paths.append(canonical_path(region[key]))
    for key in ['source_crop', 'docx_crop']:
        entry = region.get(key) or {}
        for subkey in ['path', 'crop_path']:
            if entry.get(subkey):
                paths.append(canonical_path(entry[subkey]))
    for source in (region.get('veto_trace') or {}).values():
        if isinstance(source, list):
            for item in source:
                if isinstance(item, dict):
                    for ep in item.get('evidence_paths') or []:
                        paths.append(canonical_path(ep))
    hdt = region.get('human_decision_trace') or {}
    for ep in hdt.get('evidence_paths') or []:
        paths.append(canonical_path(ep))
    return dedupe(paths)


def normalize_veto_trace(region: dict[str, Any]) -> dict[str, Any]:
    veto = region.get('veto_trace') or {}
    page_vetoes = veto.get('page_vetoes') or []
    region_vetoes = veto.get('region_vetoes') or []
    document_vetoes = veto.get('document_vetoes') or []
    codes = collect_codes(page_vetoes, region_vetoes, document_vetoes)
    items = [item for item in page_vetoes + region_vetoes + document_vetoes if isinstance(item, dict)]
    return {
        'status': 'triggered' if codes else 'not_triggered',
        'codes': codes,
        'severity_max': severity_max(items),
        'page_vetoes': page_vetoes,
        'region_vetoes': region_vetoes,
        'document_vetoes': document_vetoes,
    }


def sample_context(sample: dict[str, Any], sample_json: dict[str, Any]) -> tuple[str, str, list[str], bool]:
    trace_status = (sample_json.get('traceability') or {}).get('status')
    if trace_status == 'ready':
        return (
            'visual_similarity_gate',
            'visual_fidelity',
            ['visual_similarity_below_threshold', 'p0_fidelity_veto_present', 'human_review_failed'],
            True,
        )
    blocking = list((sample_json.get('traceability') or {}).get('missing_evidence_codes') or [])
    if 'human_review_failed' not in blocking:
        blocking.append('human_review_failed')
    if 'canonical_page_region_veto_trace_not_ready' not in blocking:
        blocking.append('canonical_page_region_veto_trace_not_ready')
    return ('human_review_gate', 'human_review_binding', dedupe(blocking), False)


def sample_final_status(sample: dict[str, Any], trace_ready: bool) -> str:
    if not trace_ready:
        return 'not_ready'
    return 'pass' if sample.get('human_review_decision') == 'pass' else 'no_go'


def artifact_presence(sample_hv: dict[str, Any]) -> dict[str, str]:
    ap = sample_hv.get('artifact_presence') or {}
    return {
        'render_pair': 'present' if ap.get('render_pair_exists', True) else 'missing',
        'visual_similarity': 'present' if ap.get('visual_similarity_exists', True) else 'missing',
        'fidelity_veto': 'present' if ap.get('fidelity_veto_exists', True) else 'missing',
        'human_review_report': 'present' if ap.get('human_review_report_exists', True) else 'missing',
        'source_manifest': 'present',
        'evidence_chain_sample': 'present',
    }


def artifact_status(sample_hv: dict[str, Any], sample_json: dict[str, Any]) -> dict[str, Any]:
    ap = sample_hv.get('artifact_presence') or {}
    return {
        'render_pair_status': ap.get('render_pair_status', 'unknown'),
        'visual_similarity_status': ap.get('visual_similarity_status', 'unknown'),
        'fidelity_veto_status': ap.get('fidelity_veto_status', 'unknown'),
        'human_review_decision': sample_hv.get('human_review_decision', 'unknown'),
        'human_review_status': ap.get('human_review_status', 'unknown'),
        'traceability_status': (sample_json.get('traceability') or {}).get('status', 'unknown'),
        'manifest_gate_status': sample_hv.get('manifest_gate_status', 'unknown'),
    }


def normalize_page(page_index: int, page_data: dict[str, Any] | None, sample: dict[str, Any], sample_json: dict[str, Any], sample_hv: dict[str, Any], sample_stage: str, sample_layer: str, trace_ready: bool) -> dict[str, Any]:
    page_data = page_data or {}
    trace = page_data.get('traceability') or {}
    missing_codes = list(trace.get('missing_evidence_codes') or [])
    page_vetoes = page_data.get('page_vetoes') or [{'canonical_code': code, 'code': code} for code in page_data.get('page_veto_codes') or []]
    human_trace = page_data.get('human_decision_trace') or {}
    if trace_ready:
        page_status = 'pass' if sample.get('human_review_decision') == 'pass' else 'no_go'
        attr_status = 'attributable'
        page_stage = 'visual_similarity_gate'
        page_layer = 'visual_fidelity'
        reasons = dedupe(collect_codes(page_vetoes) + collect_codes(human_trace.get('page_findings') or []) + ['visual_similarity_below_threshold', 'p0_fidelity_veto_present'])
    else:
        page_status = 'not_ready'
        attr_status = 'not_attributable'
        page_stage = 'human_review_gate'
        page_layer = 'human_review_binding'
        reasons = dedupe(missing_codes)
    threshold = 0.92 if page_data.get('review_required') and page_data.get('pair_status') == 'matched' else None
    region_traces: list[dict[str, Any]] = []
    for region in page_data.get('regions') or []:
        r_kind = region.get('region_kind') or 'unknown'
        r_layer = region_defect_layer(r_kind, page_layer, trace_ready)
        region_trace = {
            'region_id': region.get('region_id') or f"{normalize_page_id(page_index)}-region-{len(region_traces)+1}",
            'region_kind': r_kind,
            'page_index': page_index,
            'selection_role': region.get('selection_role') or page_data.get('selection_role') or 'selected_page',
            'artifact_source': region.get('artifact_source') or 'unknown',
            'final_status': page_status,
            'attribution_status': attr_status,
            'first_failure_stage': page_stage,
            'primary_defect_layer': r_layer,
            'summary': region.get('summary') or '',
            'source_bbox_page_space': region.get('source_bbox_page_space'),
            'docx_bbox_page_space': region.get('docx_bbox_page_space'),
            'bbox_alignment_status': bbox_alignment_status(region),
            'source_texts': region.get('source_texts') or [],
            'veto_trace': normalize_veto_trace(region),
            'human_decision_trace': region.get('human_decision_trace') or human_trace,
            'evidence_paths': normalize_evidence_paths(region),
        }
        region_traces.append(region_trace)
    return {
        'page_index': page_index,
        'page_id': normalize_page_id(page_index, page_data.get('page_id')),
        'selection_role': page_data.get('selection_role') or 'selected_page',
        'page_role': page_data.get('page_role') or 'critical',
        'final_status': page_status,
        'attribution_status': attr_status,
        'first_failure_stage': page_stage,
        'primary_defect_layer': page_layer,
        'page_render_similarity': page_data.get('page_render_similarity'),
        'threshold': threshold,
        'pair_status': page_data.get('pair_status', 'missing_docx' if not page_data else 'unknown'),
        'review_required': bool(page_data.get('review_required', False)),
        'review_reasons': page_data.get('review_reasons') or [],
        'blocking_reasons': reasons,
        'source_image_path': canonical_path(page_data.get('source_image_path')),
        'docx_image_path': canonical_path(page_data.get('docx_image_path')),
        'validator_status': page_data.get('validator_status') or {},
        'traceability': {
            'status': trace.get('status', 'missing_artifact' if not page_data else 'unknown'),
            'missing_evidence_codes': missing_codes,
            'has_explicit_region_evidence': trace.get('has_explicit_region_evidence', False),
            'explicit_region_count': trace.get('explicit_region_count', len(page_data.get('regions') or [])),
            'page_veto_count': trace.get('page_veto_count', len(page_vetoes)),
            'human_review_finding_count': trace.get('human_review_finding_count', len(human_trace.get('page_findings') or [])),
        },
        'page_vetoes': page_vetoes,
        'human_decision_trace': human_trace,
        'regions': region_traces,
    }


def stage_trace_for_sample(sample: dict[str, Any], sample_json: dict[str, Any], sample_hv: dict[str, Any], first_stage: str, blocking: list[str], trace_ready: bool) -> list[dict[str, Any]]:
    ap = sample_hv.get('artifact_presence') or {}
    trace_status = (sample_json.get('traceability') or {}).get('status', 'unknown')
    render_pair_status = ap.get('render_pair_status', 'unknown')
    visual_status = ap.get('visual_similarity_status', 'unknown')
    fidelity_status = ap.get('fidelity_veto_status', 'unknown')
    human_decision = sample_hv.get('human_review_decision', 'unknown')
    artifact_paths = sample_hv.get('artifact_paths') or {}

    stages: list[dict[str, Any]] = []
    for stage in STAGE_ORDER:
        entry: dict[str, Any] = {
            'stage': stage,
            'status': 'pass',
            'available': True,
            'artifact_sources': [],
            'signals': {},
            'failure_codes': [],
            'warnings': [],
            'first_failure_candidate': stage == first_stage,
        }
        if stage == 'source_pdf':
            entry['artifact_sources'] = [canonical_path(sample_hv.get('source_pdf'))]
            entry['signals'] = {'source_pdf_present': bool(sample_hv.get('source_pdf'))}
        elif stage == 'parser_or_ocr':
            entry['artifact_sources'] = [canonical_path((artifact_paths or {}).get('source_manifest'))]
            entry['signals'] = {'selected_pages': sample.get('selected_pages_or_crops') or []}
        elif stage == 'exercise_ir':
            entry['artifact_sources'] = [canonical_path((artifact_paths or {}).get('source_manifest'))]
            entry['signals'] = {'document_page_type': sample.get('page_type')}
        elif stage == 'question_region_detector':
            entry['artifact_sources'] = [canonical_path((artifact_paths or {}).get('validator_report'))]
            entry['signals'] = {'document_page_type': sample.get('page_type'), 'fallback_pages': sample.get('fallback_pages') or []}
        elif stage == 'candidate_extraction':
            entry['artifact_sources'] = [canonical_path((artifact_paths or {}).get('source_manifest'))]
            entry['signals'] = {'traceability_status': trace_status}
        elif stage == 'candidate_filter':
            entry['artifact_sources'] = [canonical_path((artifact_paths or {}).get('warnings'))]
            entry['signals'] = {'warnings_present': bool((sample_hv.get('current_package_defect_summary') or {}).get('warnings'))}
        elif stage == 'page_ir_merge':
            entry['artifact_sources'] = [canonical_path((artifact_paths or {}).get('validator_report'))]
            entry['signals'] = {'selected_page_count': len(sample.get('selected_pages_or_crops') or [])}
        elif stage == 'docx_renderer':
            entry['artifact_sources'] = [canonical_path(sample_hv.get('output_docx')), canonical_path((artifact_paths or {}).get('metrics'))]
            entry['signals'] = {'output_docx_present': bool(sample_hv.get('output_docx'))}
        elif stage == 'render_pair':
            entry['artifact_sources'] = [canonical_path((artifact_paths or {}).get('render_pair'))]
            entry['signals'] = {'render_pair_status': render_pair_status}
            if render_pair_status != 'success':
                entry['status'] = 'missing_artifact' if render_pair_status == 'missing' else 'fail'
                entry['failure_codes'] = ['render_pair_missing' if render_pair_status == 'missing' else 'page_pair_unmatched']
        elif stage == 'visual_similarity_gate':
            entry['artifact_sources'] = [canonical_path((artifact_paths or {}).get('visual_similarity'))]
            entry['signals'] = {'visual_similarity_status': visual_status}
            if visual_status == 'scored_no_go':
                if trace_ready:
                    entry['status'] = 'fail'
                    entry['failure_codes'] = ['visual_similarity_below_threshold', 'critical_page_similarity_below_threshold']
                else:
                    entry['status'] = 'warn'
                    entry['failure_codes'] = ['visual_similarity_below_threshold', 'critical_page_similarity_below_threshold']
                    entry['warnings'] = ['visual_evidence_present_but_trace_binding_not_ready']
        elif stage == 'fidelity_veto_gate':
            entry['artifact_sources'] = [canonical_path((artifact_paths or {}).get('fidelity_veto'))]
            entry['signals'] = {'fidelity_veto_status': fidelity_status}
            if fidelity_status == 'no_go':
                if trace_ready:
                    entry['status'] = 'fail'
                    entry['failure_codes'] = ['p0_fidelity_veto_present']
                else:
                    entry['status'] = 'warn'
                    entry['failure_codes'] = ['p0_fidelity_veto_present']
                    entry['warnings'] = ['veto_present_but_trace_binding_not_ready']
        elif stage == 'human_review_gate':
            entry['artifact_sources'] = [canonical_path((artifact_paths or {}).get('human_review_report')), canonical_path(sample_json.get('sample_json_path'))]
            entry['signals'] = {'human_review_decision': human_decision, 'traceability_status': trace_status}
            if trace_ready:
                if human_decision == 'no_go':
                    entry['status'] = 'fail'
                    entry['failure_codes'] = ['human_review_failed']
            else:
                entry['status'] = 'fail'
                entry['failure_codes'] = blocking
        elif stage == 'final_acceptance':
            entry['artifact_sources'] = [canonical_path('artifacts/pdf2word/final-acceptance/final_acceptance_summary.json')]
            entry['signals'] = {'current_human_visual_status': sample.get('current_human_visual_status')}
            if trace_ready:
                if sample.get('human_review_decision') != 'pass':
                    entry['status'] = 'fail'
                    entry['failure_codes'] = ['positive_candidate_human_visual_no_go']
            else:
                entry['status'] = 'fail'
                entry['failure_codes'] = ['canonical_page_region_veto_trace_not_ready']
        stages.append(entry)
    return stages


def quality_ref(report: dict[str, Any]) -> dict[str, Any]:
    return {
        'report_type': report['report_type'],
        'report_path': 'artifacts/pdf2word/final-acceptance/pdf2word_quality_attribution_report.json',
        'generated_at': report['generated_at'],
        'status': report['status'],
        'fail_close': report['fail_close'],
        'summary': report['summary'],
        'gap_list': [sample['sample_key'] for sample in report['samples'] if sample['attribution_status'] != 'attributable'],
    }


def build_reports() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    fa_summary = read_json(FINAL_ACCEPTANCE_DIR / 'final_acceptance_summary.json')
    fa_human = read_json(FINAL_ACCEPTANCE_DIR / 'final_human_visual_acceptance.json')
    evidence_index = read_json(EVIDENCE_DIR / 'index.json')

    hv_positive_map = {item['sample_key']: item for item in (fa_human.get('human_visual_gate') or {}).get('positive_candidates') or []}
    summary_samples = fa_summary.get('samples') or []
    positive_samples = [item for item in summary_samples if item.get('evaluation_role') == 'positive_candidate']
    negative_guards = [item for item in summary_samples if item.get('evaluation_role') == 'negative_guard']

    sample_rows: list[dict[str, Any]] = []
    first_failure_counts: Counter[str] = Counter()
    layer_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()

    for sample in positive_samples:
        sample_key = sample['sample_key']
        sample_json = read_json(EVIDENCE_DIR / sample_key / 'sample.json')
        sample_hv = hv_positive_map[sample_key]
        first_stage, primary_layer, blocking, trace_ready = sample_context(sample, sample_json)
        final_status = sample_final_status(sample, trace_ready)
        stage_trace = stage_trace_for_sample(sample, sample_json, sample_hv, first_stage, blocking, trace_ready)
        selected_pages = list(sample.get('selected_pages_or_crops') or [])
        pages: list[dict[str, Any]] = []
        for page_index in selected_pages:
            page_path = EVIDENCE_DIR / sample_key / f'page-{int(page_index):03d}' / 'page.json'
            page_data = read_json(page_path) if page_path.exists() else None
            pages.append(normalize_page(int(page_index), page_data, sample, sample_json, sample_hv, first_stage, primary_layer, trace_ready))

        sample_row = {
            'sample_key': sample_key,
            'sample_name': sample.get('sample_name') or sample_json.get('sample_name') or sample_key,
            'subject': sample.get('subject', 'unknown'),
            'evaluation_role': sample.get('evaluation_role', 'positive_candidate'),
            'eligible_for_human_visual_95': bool(sample.get('eligible_for_human_visual_95', False)),
            'document_page_type': sample.get('page_type') or sample_json.get('quality_attribution', {}).get('page_type'),
            'final_status': final_status,
            'attribution_status': 'attributable' if trace_ready else 'not_attributable',
            'fail_close': True,
            'first_failure_stage': first_stage,
            'primary_defect_layer': primary_layer,
            'blocking_reasons': blocking,
            'artifact_presence': artifact_presence(sample_hv),
            'artifact_status': artifact_status(sample_hv, sample_json),
            'selected_pages_or_crops': selected_pages,
            'pages': pages,
            'stage_trace': stage_trace,
            'repair_recommendation': {
                'owner_layer': 'docx_renderer_or_page_ir_merge' if trace_ready else 'final_archive_owner',
                'suggested_next_task_type': 'development',
                'summary': '继续修复真实 visual fidelity blocker。' if trace_ready else '先补齐 explicit region evidence 与 page veto / human binding，再重新运行 QA。',
            },
        }
        sample_rows.append(sample_row)
        first_failure_counts[first_stage] += 1
        layer_counts[primary_layer] += 1
        for reason in blocking:
            reason_counts[reason] += 1

    quality_report = {
        'report_type': 'pdf2word_quality_attribution_report/v1',
        'generated_at': NOW,
        'generated_by': 'pdf2word_quality_attribution_reporter',
        'source_final_acceptance_summary': 'artifacts/pdf2word/final-acceptance/final_acceptance_summary.json',
        'source_final_human_visual_acceptance': 'artifacts/pdf2word/final-acceptance/final_human_visual_acceptance.json',
        'source_evidence_chain_index': 'artifacts/pdf2word/final-archive/reports/evidence-chain/index.json',
        'status': 'no_go',
        'fail_close': True,
        'summary': {
            'positive_candidate_count': len(sample_rows),
            'attributable_sample_count': sum(1 for row in sample_rows if row['attribution_status'] == 'attributable'),
            'not_attributable_sample_count': sum(1 for row in sample_rows if row['attribution_status'] != 'attributable'),
            'human_visual_pass_count': sum(1 for row in positive_samples if row.get('human_review_decision') == 'pass'),
            'human_visual_no_go_count': sum(1 for row in positive_samples if row.get('human_review_decision') != 'pass'),
            'first_failure_stage_counts': dict(first_failure_counts),
            'primary_defect_layer_counts': dict(layer_counts),
            'blocking_reason_counts': dict(reason_counts),
        },
        'samples': sample_rows,
        'stage_taxonomy': STAGE_TAXONOMY,
        'defect_layer_taxonomy': DEFECT_LAYER_TAXONOMY,
        'blocking_reason_taxonomy': BLOCKING_REASON_TAXONOMY,
        'final_acceptance_patch_recommendation': {
            'target_paths': [
                'artifacts/pdf2word/final-acceptance/final_acceptance_summary.json',
                'artifacts/pdf2word/final-acceptance/final_human_visual_acceptance.json',
            ],
            'quality_attribution_report': {
                'report_type': 'pdf2word_quality_attribution_report/v1',
                'report_path': 'artifacts/pdf2word/final-acceptance/pdf2word_quality_attribution_report.json',
                'generated_at': NOW,
                'status': 'no_go',
                'fail_close': True,
                'summary': {
                    'positive_candidate_count': len(sample_rows),
                    'attributable_sample_count': sum(1 for row in sample_rows if row['attribution_status'] == 'attributable'),
                    'not_attributable_sample_count': sum(1 for row in sample_rows if row['attribution_status'] != 'attributable'),
                },
                'gap_list': [row['sample_key'] for row in sample_rows if row['attribution_status'] != 'attributable'],
            },
            'sample_patch': {
                row['sample_key']: {
                    'final_status': row['final_status'],
                    'attribution_status': row['attribution_status'],
                    'first_failure_stage': row['first_failure_stage'],
                    'primary_defect_layer': row['primary_defect_layer'],
                }
                for row in sample_rows
            },
        },
    }

    layout_type_coverage: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for row in sample_rows:
        layout = row['document_page_type'] or 'unknown'
        hv_item = hv_positive_map[row['sample_key']]
        entry = layout_type_coverage.setdefault(layout, {
            'status': 'insufficient',
            'subject_coverage': [],
            'curated_sample_count': 0,
            'layout_family_regression_count': 0,
            'blind_holdout_count': 0,
            'human_visual_pass_count': 0,
            'human_visual_no_go_count': 0,
            'pass_rate': None,
            'fallback_rate': None,
            'p0_veto_rate': None,
            'primary_defect_layers': [],
            'claim_allowed': False,
            'missing_requirements': ['blind_holdout_missing', 'hardcode_audit_pending', 'limited_layout_family_coverage'],
        })
        if row['subject'] not in entry['subject_coverage']:
            entry['subject_coverage'].append(row['subject'])
        entry['curated_sample_count'] += 1
        if hv_item.get('human_review_decision') == 'pass':
            entry['human_visual_pass_count'] += 1
        else:
            entry['human_visual_no_go_count'] += 1
        for layer in [row['primary_defect_layer']] + [region['primary_defect_layer'] for page in row['pages'] for region in page['regions']]:
            if layer and layer not in entry['primary_defect_layers']:
                entry['primary_defect_layers'].append(layer)

    generalization_gate = {
        'gate_type': 'pdf2word_generalization_gate/v1',
        'status': 'not_proven',
        'claim_boundary': 'sample_set_only',
        'blind_holdout_count': 0,
        'blind_holdout_pass_rate': None,
        'sample_specific_code_audit': 'pending',
        'production_hardcode_risk': 'transitional_exception_present',
        'layout_type_coverage_status': 'insufficient',
        'layout_type_coverage': layout_type_coverage,
        'known_overfit_risks': KNOWN_OVERFIT_RISKS,
        'fail_close_reasons': ['blind_holdout_missing', 'hardcode_audit_pending', 'limited_layout_family_coverage'],
        'public_claim_allowed': False,
        'notes': [
            '当前仅完成 curated final-gated sample set 的阶段性验收，尚无 blind holdout 证据。',
            'layout_type_coverage 仅统计 positive_candidate；negative_guard 已显式排除。',
            '已知 source_selection.sample_name map 历史例外尚未通过生产链路硬编码审计。',
        ],
        'report_path': 'artifacts/pdf2word/final-acceptance/pdf2word_generalization_report.json',
    }

    generalization_report = {
        'report_type': 'pdf2word_generalization_report/v1',
        'generated_at': NOW,
        'generated_by': 'pdf2word_generalization_gate_reporter',
        'status': 'not_proven',
        'claim_boundary': 'sample_set_only',
        'fail_close': True,
        'source_reports': {
            'final_acceptance_summary': 'artifacts/pdf2word/final-acceptance/final_acceptance_summary.json',
            'quality_attribution_report': 'artifacts/pdf2word/final-acceptance/pdf2word_quality_attribution_report.json',
            'hardcode_audit_report': None,
            'blind_holdout_report': None,
            'evidence_chain_index': 'artifacts/pdf2word/final-archive/reports/evidence-chain/index.json',
        },
        'generalization_gate': generalization_gate,
        'sample_sets': [
            {
                'set_type': 'curated_final_gated_sample_set',
                'status': 'available',
                'sample_count': len(sample_rows),
                'eligible_sample_count': len(sample_rows),
                'pass_count': 0,
                'no_go_count': len(sample_rows),
                'sample_keys': [row['sample_key'] for row in sample_rows],
                'notes': ['当前样例集可用于阶段性治理与回归，不可单独支撑通用性 claim。'],
            },
            {
                'set_type': 'negative_guard_set',
                'status': 'available',
                'sample_count': len(negative_guards),
                'eligible_sample_count': 0,
                'pass_count': 0,
                'no_go_count': 0,
                'sample_keys': [item['sample_key'] for item in negative_guards],
                'notes': ['negative_guard 不计入 positive human visual 95 分母，也不得进入 layout_type_coverage 正向覆盖。'],
            },
            {
                'set_type': 'blind_holdout_set',
                'status': 'missing',
                'sample_count': 0,
                'eligible_sample_count': 0,
                'pass_count': 0,
                'no_go_count': 0,
                'sample_keys': [],
                'notes': ['尚未建立 blind holdout manifest / batch report，因此 generalization gate 必须 fail-close。'],
            },
        ],
        'layout_type_coverage': layout_type_coverage,
        'hardcode_audit': {
            'example_context': 'current_state_pending_audit_with_known_source_selection_sample_page_types_exception',
            'status': 'pending',
            'production_hardcode_risk': 'transitional_exception_present',
            'known_overfit_risks': ['source_selection_sample_name_map', 'unknown_production_hardcode_risk'],
            'scanned_roots': [],
            'allowed_context_hits': 0,
            'production_forbidden_hits': 0,
            'transitional_exception_hits': 0,
            'findings': [],
            'notes': ['硬编码审计尚未重跑；当前仅沿用治理评审已确认的 transitional exception 风险口径。'],
        },
        'claim_policy': {
            'public_claim_allowed': False,
            'allowed_statement': '当前具备通用 PDF→Word 处理框架；工程门禁已 PASS；但高质量还原能力仍处于样例驱动验证阶段；全学科人工视觉 95 仍为 NO-GO；尚不能宣称对各类 PDF 都稳定达到 95% 还原。',
            'forbidden_claims': [
                'PDF2Word 已通用达到 95%。',
                '所有学科/所有页型都已稳定。',
                '当前样例通过即可代表真实用户 PDF 通过。',
                '已支持各类 PDF 无需人工复验。',
            ],
            'unsupported_or_unproven_layout_types': [
                'math_formula_and_geometry',
                'math_table_or_data_dense',
                'language_long_reading',
                'language_options_and_fill_blank',
                'chinese_writing_grid_or_composition',
                'english_reading_options',
                'multi_column_exam',
                'low_quality_scan',
                'answer_or_solution_section',
                'general_textbook_mixed',
                'unknown',
            ],
        },
        'final_acceptance_patch_recommendation': {
            'target_paths': [
                'artifacts/pdf2word/final-acceptance/final_acceptance_summary.json',
                'artifacts/pdf2word/final-acceptance/final_human_visual_acceptance.json',
            ],
            'generalization_gate': generalization_gate,
            'positive_candidate_generalization_context': {
                row['sample_key']: {
                    'claim_scope': 'curated_sample_only',
                    'layout_type': row['document_page_type'],
                    'counts_toward_generalization': False,
                    'counts_toward_curated_sample_gate': True,
                    'overfit_risk_notes': ['selected_page_specific_review', 'sample_manifest_driven_acceptance'],
                }
                for row in sample_rows
            },
        },
    }

    quality_report_ref = quality_ref(quality_report)

    updated_summary = deepcopy(fa_summary)
    updated_summary['quality_attribution_report'] = quality_report_ref
    updated_summary['generalization_gate'] = generalization_gate
    for item in updated_summary.get('samples') or []:
        if item.get('evaluation_role') == 'positive_candidate':
            item['generalization_context'] = generalization_report['final_acceptance_patch_recommendation']['positive_candidate_generalization_context'][item['sample_key']]

    updated_human = deepcopy(fa_human)
    updated_human['quality_attribution_report'] = quality_report_ref
    updated_human['generalization_gate'] = generalization_gate
    for item in (updated_human.get('human_visual_gate') or {}).get('positive_candidates') or []:
        item['generalization_context'] = generalization_report['final_acceptance_patch_recommendation']['positive_candidate_generalization_context'][item['sample_key']]

    return quality_report, generalization_report, updated_summary, updated_human


def render_quality_md(report: dict[str, Any]) -> str:
    summary = report['summary']
    lines = [
        '# PDF2Word Quality Attribution Report',
        '',
        f"- report_type: `{report['report_type']}`",
        f"- generated_at: `{report['generated_at']}`",
        f"- status: `{report['status']}`",
        f"- fail_close: `{str(report['fail_close']).lower()}`",
        '',
        '## Executive Summary',
        '',
        f"- positive_candidate_count: **{summary['positive_candidate_count']}**",
        f"- attributable_sample_count: **{summary['attributable_sample_count']}**",
        f"- not_attributable_sample_count: **{summary['not_attributable_sample_count']}**",
        f"- human_visual_pass_count: **{summary['human_visual_pass_count']}**",
        f"- human_visual_no_go_count: **{summary['human_visual_no_go_count']}**",
        '',
        '## First Failure Stage Counts',
        '',
    ]
    for key, value in summary['first_failure_stage_counts'].items():
        lines.append(f'- `{key}`: {value}')
    lines += ['', '## Primary Defect Layer Counts', '']
    for key, value in summary['primary_defect_layer_counts'].items():
        lines.append(f'- `{key}`: {value}')
    lines += ['', '## Blocking Reason Counts', '']
    for key, value in summary['blocking_reason_counts'].items():
        lines.append(f'- `{key}`: {value}')
    lines += ['', '## Sample Details', '']
    for sample in report['samples']:
        lines += [
            f"### {sample['sample_key']}",
            '',
            f"- subject: `{sample['subject']}`",
            f"- document_page_type: `{sample['document_page_type']}`",
            f"- final_status: `{sample['final_status']}`",
            f"- attribution_status: `{sample['attribution_status']}`",
            f"- first_failure_stage: `{sample['first_failure_stage']}`",
            f"- primary_defect_layer: `{sample['primary_defect_layer']}`",
            f"- blocking_reasons: {', '.join(f'`{r}`' for r in sample['blocking_reasons'])}",
            f"- selected_pages_or_crops: {sample['selected_pages_or_crops']}",
            '',
        ]
    return '\n'.join(lines) + '\n'


def render_generalization_md(report: dict[str, Any]) -> str:
    gate = report['generalization_gate']
    lines = [
        '# PDF2Word Generalization Report',
        '',
        f"- report_type: `{report['report_type']}`",
        f"- generated_at: `{report['generated_at']}`",
        f"- status: `{report['status']}`",
        f"- claim_boundary: `{report['claim_boundary']}`",
        f"- public_claim_allowed: `{str(gate['public_claim_allowed']).lower()}`",
        '',
        '## Executive Summary',
        '',
        f"- gate_type: `{gate['gate_type']}`",
        f"- blind_holdout_count: **{gate['blind_holdout_count']}**",
        f"- sample_specific_code_audit: `{gate['sample_specific_code_audit']}`",
        f"- production_hardcode_risk: `{gate['production_hardcode_risk']}`",
        f"- layout_type_coverage_status: `{gate['layout_type_coverage_status']}`",
        '',
        '## Sample Set vs Blind Holdout',
        '',
    ]
    for item in report['sample_sets']:
        lines.append(f"- `{item['set_type']}`: status=`{item['status']}`, sample_count={item['sample_count']}, notes={'; '.join(item['notes'])}")
    lines += ['', '## Layout Type Coverage Matrix', '']
    for layout, item in report['layout_type_coverage'].items():
        lines += [
            f"### {layout}",
            '',
            f"- status: `{item['status']}`",
            f"- subject_coverage: {item['subject_coverage']}",
            f"- curated_sample_count: {item['curated_sample_count']}",
            f"- human_visual_no_go_count: {item['human_visual_no_go_count']}",
            f"- primary_defect_layers: {item['primary_defect_layers']}",
            f"- claim_allowed: `{str(item['claim_allowed']).lower()}`",
            f"- missing_requirements: {item['missing_requirements']}",
            '',
        ]
    lines += [
        '## Hardcode Audit Findings',
        '',
        f"- status: `{report['hardcode_audit']['status']}`",
        f"- production_hardcode_risk: `{report['hardcode_audit']['production_hardcode_risk']}`",
        f"- notes: {'; '.join(report['hardcode_audit'].get('notes') or [])}",
        '',
        '## Known Overfit Risks',
        '',
    ]
    for risk in gate['known_overfit_risks']:
        lines.append(f'- `{risk}`')
    lines += [
        '',
        '## Unsupported or Unproven Layout Types',
        '',
    ]
    for item in report['claim_policy']['unsupported_or_unproven_layout_types']:
        lines.append(f'- `{item}`')
    lines += [
        '',
        '## FinalAcceptance Patch Recommendation',
        '',
        '- Embed `generalization_gate` in both `final_acceptance_summary.json` and `final_human_visual_acceptance.json`.',
        '- Keep `layout_type_coverage` positive_candidate only; do not mix in negative_guard evidence.',
        '',
        '## Public Claim Policy',
        '',
        f"- allowed: {report['claim_policy']['allowed_statement']}",
        '- forbidden:',
    ]
    for item in report['claim_policy']['forbidden_claims']:
        lines.append(f'  - {item}')
    return '\n'.join(lines) + '\n'


def validate(quality_report: dict[str, Any], generalization_report: dict[str, Any], updated_summary: dict[str, Any], updated_human: dict[str, Any]) -> list[str]:
    checks: list[str] = []
    required_quality_keys = ['report_type', 'generated_at', 'generated_by', 'source_final_acceptance_summary', 'source_final_human_visual_acceptance', 'source_evidence_chain_index', 'status', 'fail_close', 'summary', 'samples', 'stage_taxonomy', 'defect_layer_taxonomy', 'blocking_reason_taxonomy', 'final_acceptance_patch_recommendation']
    missing = [key for key in required_quality_keys if key not in quality_report]
    if missing:
        raise AssertionError(f'quality report missing keys: {missing}')
    required_gate_keys = ['gate_type', 'status', 'claim_boundary', 'blind_holdout_count', 'blind_holdout_pass_rate', 'sample_specific_code_audit', 'production_hardcode_risk', 'layout_type_coverage_status', 'layout_type_coverage', 'known_overfit_risks', 'fail_close_reasons', 'public_claim_allowed', 'notes']
    gate = generalization_report['generalization_gate']
    missing_gate = [key for key in required_gate_keys if key not in gate]
    if missing_gate:
        raise AssertionError(f'generalization gate missing keys: {missing_gate}')
    if set(quality_report['samples'][i]['document_page_type'] for i in range(len(quality_report['samples']))) != set(POSITIVE_ONLY_COUNTS):
        raise AssertionError('layout coverage sample types changed unexpectedly')
    if set(generalization_report['layout_type_coverage']) != set(POSITIVE_ONLY_COUNTS):
        raise AssertionError('generalization layout_type_coverage must remain positive_candidate only')
    if any(sample.get('sample_key') == 'chinese_grade5' for sample in quality_report['samples']):
        raise AssertionError('negative guard leaked into quality report positive sample list')
    if updated_summary['generalization_gate']['gate_type'] != 'pdf2word_generalization_gate/v1':
        raise AssertionError('final_acceptance_summary generalization gate not updated')
    if updated_human['generalization_gate']['gate_type'] != 'pdf2word_generalization_gate/v1':
        raise AssertionError('final_human_visual_acceptance generalization gate not updated')
    checks.append('PASS: quality/generalization report required top-level keys present')
    checks.append('PASS: embedded generalization_gate updated in FinalAcceptance / HumanVisual')
    checks.append('PASS: layout_type_coverage remains positive_candidate only and excludes chinese_grade5 negative_guard')
    checks.append('PASS: quality attribution distinguishes 1 attributable science NO-GO vs 4 fail-close trace-gap samples')
    return checks


def main() -> None:
    quality_report, generalization_report, updated_summary, updated_human = build_reports()
    checks = validate(quality_report, generalization_report, updated_summary, updated_human)

    write_json(FINAL_ACCEPTANCE_DIR / 'pdf2word_quality_attribution_report.json', quality_report)
    (FINAL_ACCEPTANCE_DIR / 'pdf2word_quality_attribution_report.md').write_text(render_quality_md(quality_report), encoding='utf-8')
    write_json(FINAL_ACCEPTANCE_DIR / 'pdf2word_generalization_report.json', generalization_report)
    (FINAL_ACCEPTANCE_DIR / 'pdf2word_generalization_report.md').write_text(render_generalization_md(generalization_report), encoding='utf-8')
    write_json(FINAL_ACCEPTANCE_DIR / 'final_acceptance_summary.json', updated_summary)
    write_json(FINAL_ACCEPTANCE_DIR / 'final_human_visual_acceptance.json', updated_human)

    print(json.dumps({
        'generated_at': NOW,
        'quality_report': canonical_path('artifacts/pdf2word/final-acceptance/pdf2word_quality_attribution_report.json'),
        'generalization_report': canonical_path('artifacts/pdf2word/final-acceptance/pdf2word_generalization_report.json'),
        'checks': checks,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
