from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

WORKTREE = Path('/Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/DOCX-6529460c')
sys.path.insert(0, str(WORKTREE / 'backend'))

from app.services.pdf_to_word.page_renderer import build_render_pair_evidence
from app.services.pdf_to_word.visual_similarity_gate import build_visual_similarity_report_from_render_pair

ARCHIVE_ROOT = Path('/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental')
SAMPLES = {
    '五下科学': ('science', 'science_experiment_table_and_image_mixed'),
    '数学八年级': ('math', 'math_exercise_with_sparse_image_and_table'),
    '数学试卷': ('math', 'math_exam_image_dense'),
    '英语八年级': ('english', 'language_exercise_sparse_media_with_fallback_pages'),
}
RENDER_DPI = 96
now = datetime.now().astimezone().isoformat(timespec='seconds')
summary = []


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def current_summary(sample_dir: Path) -> dict:
    rp = load_json(sample_dir / 'render_pair.json')
    vs = load_json(sample_dir / 'visual_similarity.json')
    hr = load_json(sample_dir / 'human_review_report.json')
    return {
        'render_pair_status': rp.get('status'),
        'render_pair_failure_code': rp.get('failure_code'),
        'visual_similarity_status': vs.get('status'),
        'visual_similarity_failure_code': vs.get('failure_code'),
        'artifact_ready_for_scoring': vs.get('artifact_ready_for_scoring'),
        'sample_verdict': hr.get('sample_verdict') or hr.get('human_visual_decision'),
    }


for sample_name, (subject, page_type) in SAMPLES.items():
    sample_dir = ARCHIVE_ROOT / sample_name
    before = current_summary(sample_dir)
    source_manifest_path = sample_dir / 'source_manifest.json'
    source_manifest = load_json(source_manifest_path)
    source_artifacts = source_manifest.get('source_artifacts') or {}
    source_pdf_path = Path(source_artifacts['source_pdf_path'])
    output_docx_path = Path(source_artifacts['output_docx_path'])
    evidence_root = sample_dir / 'render_pair_artifacts'

    render_pair = build_render_pair_evidence(
        source_pdf_path=source_pdf_path,
        docx_path=output_docx_path,
        evidence_root=evidence_root,
        render_dpi=RENDER_DPI,
        allow_text_fallback=True,
    )
    render_pair['generated_at'] = now
    render_pair['sample_name'] = sample_name
    render_pair['subject'] = subject
    render_pair['document_page_type'] = page_type
    write_json(sample_dir / 'render_pair.json', render_pair)

    visual = build_visual_similarity_report_from_render_pair(
        render_pair,
        sample_name=sample_name,
        subject=subject,
        document_page_type=page_type,
        requested_mode='quality/hybrid_async',
        parser_backend='hybrid_experimental',
    )
    visual['generated_at'] = now
    visual['evidence_paths'] = {
        'render_pair_path': str(sample_dir / 'render_pair.json'),
        'source_pdf_path': str(source_pdf_path),
        'output_docx_path': str(output_docx_path),
        'render_pair_artifacts_root': str(evidence_root),
    }
    write_json(sample_dir / 'visual_similarity.json', visual)

    old_fidelity = load_json(sample_dir / 'fidelity_veto.json')
    old_vetoes = [v for v in old_fidelity.get('vetoes') or [] if isinstance(v, dict)]
    # Remove obsolete renderer-missing wording; preserve non-renderer P0 facts.
    preserved_vetoes = []
    for veto in old_vetoes:
        code = str(veto.get('canonical_code') or veto.get('code') or '')
        summary_text = str(veto.get('summary') or '')
        if code == 'critical_fallback_not_visually_close_to_source' and '未获得真实 render pair' in summary_text:
            veto = dict(veto)
            veto['summary'] = '真实 render pair 已生成；fallback/文本页与源 PDF 仍未达到可恢复人工视觉95的接近度。'
        preserved_vetoes.append(veto)
    if not visual.get('gate_passed'):
        preserved_vetoes.append({
            'code': 'visual_similarity_below_threshold',
            'canonical_code': 'visual_similarity_below_threshold',
            'severity': 'p0',
            'scope': 'document',
            'page_index': None,
            'region_kind': None,
            'region_id': None,
            'summary': '真实 render_pair 已可评分，但 document/page visual similarity 低于人工95门禁阈值。',
            'category': 'visual_similarity',
            'label': '真实渲染相似度低于门禁阈值',
            'triggered': True,
            'evidence_paths': [
                str(sample_dir / 'render_pair.json'),
                str(sample_dir / 'visual_similarity.json'),
            ],
        })
    # Deduplicate by code + page index + summary.
    deduped = []
    seen = set()
    for veto in preserved_vetoes:
        key = (veto.get('canonical_code') or veto.get('code'), veto.get('page_index'), veto.get('summary'))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(veto)

    p0_count = sum(1 for v in deduped if str(v.get('severity') or '').lower() == 'p0' and v.get('triggered', True))
    fidelity = {
        **old_fidelity,
        'generated_at': now,
        'status': 'no_go' if p0_count or not visual.get('gate_passed') else 'review_required',
        'overall_score': visual.get('aggregate', {}).get('overall_page_similarity_mean'),
        'human_review_required': True,
        'page_scores': visual.get('page_scores') or [],
        'render_pairs': [
            {
                'page_index': pair.get('page_index'),
                'pair_status': pair.get('pair_status'),
                'alignment_mode': 'page_index',
                'source_image_path': pair.get('source_image_path'),
                'docx_image_path': pair.get('docx_image_path'),
            }
            for pair in (render_pair.get('render_pairs') or [])
        ],
        'vetoes': deduped,
        'page_vetoes': [],
        'region_vetoes': [],
        'p0_veto_count': p0_count,
        'renderer_strategy': render_pair.get('renderer_strategy'),
        'fallback_used': render_pair.get('fallback_used'),
        'notes': [
            'real render_pair evidence regenerated for DOCX scoring chain',
            'LibreOffice/soffice unavailable; used deterministic python_docx_text_fallback renderer, therefore no_go remains quality evidence rather than a pass',
        ],
    }
    write_json(sample_dir / 'fidelity_veto.json', fidelity)

    blocking_reasons = []
    if not visual.get('gate_passed'):
        blocking_reasons.append('visual_similarity_below_threshold')
    if p0_count:
        blocking_reasons.append('p0_fidelity_veto_present')
    if not blocking_reasons:
        blocking_reasons.append('manual_human_review_required')
    human = {
        'report_type': 'pdf_to_word_human_visual_review_report',
        'contract_version': 'pdf_to_word_human_visual_review/v1',
        'generated_at': now,
        'sample_name': sample_name,
        'subject': subject,
        'document_page_type': page_type,
        'artifact_ready_for_scoring': bool(visual.get('artifact_ready_for_scoring')),
        'render_pair_status': render_pair.get('status'),
        'render_pair_failure_code': render_pair.get('failure_code'),
        'visual_similarity_status': visual.get('status'),
        'visual_similarity_failure_code': visual.get('failure_code'),
        'visual_similarity_gate_passed': bool(visual.get('gate_passed')),
        'overall_page_similarity_mean': visual.get('aggregate', {}).get('overall_page_similarity_mean'),
        'min_page_similarity': visual.get('aggregate', {}).get('min_page_similarity'),
        'fidelity_veto_status': fidelity.get('status'),
        'fidelity_veto_p0_count': p0_count,
        'human_visual_decision': 'go' if visual.get('gate_passed') and p0_count == 0 else 'no_go',
        'eligible_for_human_visual_95': bool(visual.get('gate_passed') and p0_count == 0),
        'sample_verdict': 'go' if visual.get('gate_passed') and p0_count == 0 else 'no_go',
        'blocking_reasons': blocking_reasons,
        'evidence_paths': {
            'render_pair_path': str(sample_dir / 'render_pair.json'),
            'visual_similarity_path': str(sample_dir / 'visual_similarity.json'),
            'fidelity_veto_path': str(sample_dir / 'fidelity_veto.json'),
            'source_manifest_path': str(source_manifest_path),
        },
        'review_notes': [
            'renderer unavailable blockage has been removed: render_pair and visual_similarity are now based on concrete rendered artifacts.',
            'Current verdict intentionally remains no_go where measured similarity/P0 vetoes fail the 95 human visual rubric.',
        ],
    }
    write_json(sample_dir / 'human_review_report.json', human)

    source_artifacts.update({
        'render_pair_path': str(sample_dir / 'render_pair.json'),
        'visual_similarity_path': str(sample_dir / 'visual_similarity.json'),
        'fidelity_veto_path': str(sample_dir / 'fidelity_veto.json'),
        'human_review_report_path': str(sample_dir / 'human_review_report.json'),
        'render_pair_artifacts_root': str(evidence_root),
        'docx_renderer_strategy': render_pair.get('renderer_strategy'),
        'docx_renderer_fallback_used': bool(render_pair.get('fallback_used')),
        'canonical_visual_evidence_materialized': True,
        'canonical_visual_evidence_scoring_ready': bool(visual.get('artifact_ready_for_scoring')),
    })
    generated = list(source_manifest.get('generated_files') or [])
    for item in ['render_pair.json', 'visual_similarity.json', 'fidelity_veto.json', 'human_review_report.json', 'render_pair_artifacts/']:
        if item not in generated:
            generated.append(item)
    source_manifest.update({
        'source_artifacts': source_artifacts,
        'generated_files': generated,
        'docx_render_dependency': {
            'preferred_native_converter': 'soffice/libreoffice --headless --convert-to pdf',
            'preferred_native_converter_available': False,
            'fallback_renderer': 'python stdlib zip/xml DOCX text extractor + Pillow PNG renderer',
            'fallback_renderer_version': render_pair.get('renderer_strategy'),
            'render_dpi': RENDER_DPI,
            'reproduce_command': 'PYTHONPATH=backend /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/python /Users/linsuchang/Desktop/work/my-agent-teams/tasks/打通DOCX渲染依赖并重跑四个正向样例真实视觉证据/artifacts/rerun_docx_visual_evidence.py',
        },
        'updated_at': now,
    })
    write_json(source_manifest_path, source_manifest)
    after = current_summary(sample_dir)
    after['renderer_strategy'] = render_pair.get('renderer_strategy')
    after['matched_pages'] = render_pair.get('matched_pages')
    after['source_page_count'] = render_pair.get('source_page_count')
    after['docx_page_count'] = render_pair.get('docx_page_count')
    after['overall_page_similarity_mean'] = visual.get('aggregate', {}).get('overall_page_similarity_mean')
    after['min_page_similarity'] = visual.get('aggregate', {}).get('min_page_similarity')
    summary.append({'sample_name': sample_name, 'before': before, 'after': after})

print(json.dumps({'generated_at': now, 'samples': summary}, ensure_ascii=False, indent=2))
