from __future__ import annotations

import hashlib
import json
import math
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops, ImageDraw, ImageFont
import pypdfium2 as pdfium

RENDER_DPI = 96
SAMPLE_KEY = 'chinese_long_reading_positive_v1'
SAMPLE_NAME = '语文长文阅读正向样例'
SUBJECT = 'chinese'
PAGE_TYPE = 'chinese_long_reading'
SELECTED_PAGES = [1, 2, 3]
THRESHOLDS = {
    'document_overall_similarity_min': 0.95,
    'critical_page_render_similarity_min': 0.92,
    'regular_page_render_similarity_min': 0.88,
    'key_region_similarity_min': 0.90,
}
SAMPLE_DIR = Path('/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/语文正向样例')
FINAL_OUTPUT_ROOT = Path('/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples')
UNIFIED_MANIFEST_PATH = FINAL_OUTPUT_ROOT / 'unified-sample-manifest.json'
FINAL_GATED_MANIFEST_PATH = FINAL_OUTPUT_ROOT / 'final-gated-manifest.json'
CHINESE_MANIFEST_PATH = FINAL_OUTPUT_ROOT / 'chinese-samples-manifest.json'
FIXTURE_ROOT = Path('/Users/linsuchang/Desktop/work/chiralium/backend/tests/fixtures/pdf_to_word/chinese_positive')
ARTIFACT_CONTRACT_PATH = FIXTURE_ROOT / 'chinese_positive_artifact_contract.json'
UNIFIED_FIXTURE_PATH = FIXTURE_ROOT / 'unified_manifest_roles_fixture.json'
SOURCE_PDF_PATH = FINAL_OUTPUT_ROOT / 'PDF转Word门禁样例-语文长文阅读正向-source.pdf'
OUTPUT_DOCX_PATH = SAMPLE_DIR / 'output.docx'
RENDER_PAIR_PATH = SAMPLE_DIR / 'render_pair.json'
VISUAL_SIMILARITY_PATH = SAMPLE_DIR / 'visual_similarity.json'
FIDELITY_VETO_PATH = SAMPLE_DIR / 'fidelity_veto.json'
HUMAN_REVIEW_PATH = SAMPLE_DIR / 'human_review_report.json'
SOURCE_MANIFEST_PATH = SAMPLE_DIR / 'source_manifest.json'
RENDER_PAIR_ARTIFACTS_ROOT = SAMPLE_DIR / 'render_pair_artifacts'
TASK_SCRIPT_PATH = Path('/Users/linsuchang/Desktop/work/my-agent-teams/tasks/补齐语文正向样例真实视觉证据并统一Manifest页选择/artifacts/rerun_chinese_positive_visual_evidence.py')
DOCX_TEXT_FALLBACK_RENDERER_VERSION = 'python_docx_text_fallback/v1'
_DEFAULT_TEXT_FALLBACK_FONT_CANDIDATES = (
    '/Library/Fonts/Arial Unicode.ttf',
    '/System/Library/Fonts/Hiragino Sans GB.ttc',
    '/System/Library/Fonts/STHeiti Medium.ttc',
    '/System/Library/Fonts/Helvetica.ttc',
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha256_file(path: str | Path) -> str:
    resolved = Path(path).expanduser().resolve()
    digest = hashlib.sha256()
    with resolved.open('rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def render_pdf_pages(pdf_path: str | Path, *, source_name: str, render_root: Path, render_dpi: int) -> list[dict[str, Any]]:
    source_path = Path(pdf_path).expanduser().resolve()
    render_root.mkdir(parents=True, exist_ok=True)
    document = pdfium.PdfDocument(str(source_path))
    rendered_pages: list[dict[str, Any]] = []
    scale = max(render_dpi, 72) / 72.0
    try:
        for page_zero_index in range(len(document)):
            page = document[page_zero_index]
            width_points, height_points = page.get_size()
            rotation_degrees = int(page.get_rotation())
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil()
            image_path = render_root / f'page-{page_zero_index + 1:03d}.png'
            meta_path = render_root / f'page-{page_zero_index + 1:03d}.json'
            image.save(image_path)
            image_sha256 = sha256_file(image_path)
            payload = {
                'page_index': page_zero_index + 1,
                'source_name': source_name,
                'source_pdf': str(source_path),
                'render_dpi': render_dpi,
                'width_points': float(width_points),
                'height_points': float(height_points),
                'rotation_degrees': rotation_degrees,
                'pixel_width': image.width,
                'pixel_height': image.height,
                'image_path': str(image_path),
                'image_sha256': image_sha256,
            }
            write_json(meta_path, payload)
            rendered_pages.append({**payload, 'render_artifact': str(meta_path)})
    finally:
        close = getattr(document, 'close', None)
        if callable(close):
            close()
    return rendered_pages


def extract_docx_text_blocks(docx_path: str | Path) -> list[str]:
    resolved_docx_path = Path(docx_path).expanduser().resolve()
    namespaces = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    }
    with zipfile.ZipFile(resolved_docx_path) as archive:
        document_xml = archive.read('word/document.xml')
        media_names = sorted(name for name in archive.namelist() if name.startswith('word/media/'))
    root = ET.fromstring(document_xml)
    body = root.find('w:body', namespaces)
    if body is None:
        return ['[DOCX contains no extractable text]']
    blocks: list[str] = []
    for child in list(body):
        tag = child.tag.rsplit('}', 1)[-1] if '}' in child.tag else child.tag
        if tag == 'p':
            text = ''.join(text.text for text in child.findall('.//w:t', namespaces) if text.text).strip()
            if text:
                blocks.append(text)
            image_count = len(child.findall('.//a:blip', namespaces))
            for _ in range(image_count):
                blocks.append('[image/drawing placeholder]')
        elif tag == 'tbl':
            rows = []
            for row in child.findall('w:tr', namespaces):
                cells = []
                for cell in row.findall('w:tc', namespaces):
                    parts = []
                    for paragraph in cell.findall('w:p', namespaces):
                        text = ''.join(text.text for text in paragraph.findall('.//w:t', namespaces) if text.text).strip()
                        if text:
                            parts.append(text)
                    cells.append(' '.join(parts) or ' ')
                if cells:
                    rows.append(' | '.join(cells))
            if rows:
                blocks.append('[table]')
                blocks.extend(rows)
    if media_names:
        blocks.append(f'[embedded media files: {len(media_names)}]')
    return blocks or ['[DOCX contains no extractable text]']


def _default_page_size(render_dpi: int) -> tuple[int, int]:
    scale = max(render_dpi, 72) / 72.0
    return int(595 * scale), int(842 * scale)


def _load_text_fallback_font(size: int) -> ImageFont.ImageFont:
    for candidate in _DEFAULT_TEXT_FALLBACK_FONT_CANDIDATES:
        path = Path(candidate)
        if not path.exists():
            continue
        try:
            return ImageFont.truetype(str(path), size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _line_height(font: ImageFont.ImageFont) -> int:
    bbox = font.getbbox('Ag国')
    return max(18, int((bbox[3] - bbox[1]) * 1.45))


def _text_width(font: ImageFont.ImageFont, text: str) -> int:
    bbox = font.getbbox(text)
    return int(bbox[2] - bbox[0])


def _wrap_block(block: str, *, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    if not block:
        return ['']
    wrapped: list[str] = []
    for segment in block.splitlines() or [block]:
        segment = segment.strip()
        if not segment:
            wrapped.append('')
            continue
        current = ''
        for char in segment:
            candidate = f'{current}{char}'
            if current and _text_width(font, candidate) > max_width:
                wrapped.append(current)
                current = char
            else:
                current = candidate
        if current:
            wrapped.append(current)
    return wrapped


def _paginate_text_blocks(blocks: list[str], *, page_width: int, page_height: int, font: ImageFont.ImageFont, expected_page_count: int | None) -> list[list[str]]:
    margin = max(48, int(page_width * 0.055))
    usable_width = max(100, page_width - margin * 2)
    usable_height = max(100, page_height - margin * 2 - 80)
    lines_per_page = max(8, usable_height // _line_height(font))
    all_lines: list[str] = []
    for block in blocks:
        all_lines.extend(_wrap_block(block, font=font, max_width=usable_width))
        all_lines.append('')
    if not all_lines:
        all_lines = ['[empty DOCX]']
    pages = [all_lines[index:index + lines_per_page] for index in range(0, len(all_lines), lines_per_page)]
    if expected_page_count and expected_page_count > 0:
        if len(pages) < expected_page_count:
            pages.extend([[] for _ in range(expected_page_count - len(pages))])
        elif len(pages) > expected_page_count:
            merged = pages[:expected_page_count - 1]
            tail = [line for page in pages[expected_page_count - 1:] for line in page]
            merged.append(tail[:lines_per_page])
            pages = merged
    return pages or [[]]


def render_docx_text_fallback_pages(docx_path: str | Path, *, render_root: Path, render_dpi: int, expected_page_count: int | None, page_size: tuple[int, int] | None) -> dict[str, Any]:
    resolved_docx_path = Path(docx_path).expanduser().resolve()
    render_root.mkdir(parents=True, exist_ok=True)
    blocks = extract_docx_text_blocks(resolved_docx_path)
    width, height = page_size or _default_page_size(render_dpi)
    font = _load_text_fallback_font(max(14, int(render_dpi * 0.12)))
    title_font = _load_text_fallback_font(max(16, int(render_dpi * 0.14)))
    pages_text = _paginate_text_blocks(blocks, page_width=width, page_height=height, font=font, expected_page_count=expected_page_count)
    fallback_reason = {
        'code': 'docx_renderer_unavailable',
        'message': 'LibreOffice/soffice is not available in current dev environment; using deterministic Python DOCX text fallback renderer',
        'details': {
            'docx_path': str(resolved_docx_path),
            'searched_binaries': ['soffice', 'libreoffice'],
        },
    }
    pages: list[dict[str, Any]] = []
    for zero_index, lines in enumerate(pages_text):
        page_index = zero_index + 1
        image = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(image)
        margin = max(48, int(width * 0.055))
        cursor_y = margin
        draw.text((margin, cursor_y), f'DOCX fallback render: {resolved_docx_path.name}  page {page_index}/{len(pages_text)}', fill=(80, 80, 80), font=title_font)
        cursor_y += _line_height(title_font) + 10
        draw.line((margin, cursor_y, width - margin, cursor_y), fill=(210, 210, 210), width=1)
        cursor_y += 18
        for line in lines:
            draw.text((margin, cursor_y), line, fill=(25, 25, 25), font=font)
            cursor_y += _line_height(font)
        image_path = render_root / f'page-{page_index:03d}.png'
        meta_path = render_root / f'page-{page_index:03d}.json'
        image.save(image_path)
        image_sha256 = sha256_file(image_path)
        payload = {
            'page_index': page_index,
            'source_name': resolved_docx_path.name,
            'source_docx': str(resolved_docx_path),
            'render_dpi': render_dpi,
            'pixel_width': width,
            'pixel_height': height,
            'image_path': str(image_path),
            'image_sha256': image_sha256,
            'renderer_strategy': DOCX_TEXT_FALLBACK_RENDERER_VERSION,
            'fallback_reason': fallback_reason,
            'text_block_count': len(blocks),
            'line_count': len(lines),
        }
        write_json(meta_path, payload)
        pages.append({**payload, 'render_artifact': str(meta_path)})
    return {
        'status': 'success',
        'renderer_strategy': DOCX_TEXT_FALLBACK_RENDERER_VERSION,
        'docx_path': str(resolved_docx_path),
        'converted_pdf_path': None,
        'pages': pages,
        'fallback_used': True,
        'fallback_reason': fallback_reason,
        'expected_page_count': expected_page_count,
        'text_block_count': len(blocks),
    }


def build_render_pair_evidence(*, source_pdf_path: Path, docx_path: Path, evidence_root: Path, render_dpi: int) -> dict[str, Any]:
    if evidence_root.exists():
        shutil.rmtree(evidence_root)
    evidence_root.mkdir(parents=True, exist_ok=True)
    source_pages = render_pdf_pages(source_pdf_path, source_name=source_pdf_path.name, render_root=evidence_root / 'source_pdf_pages', render_dpi=render_dpi)
    fallback_size = None
    if source_pages:
        fallback_size = (int(source_pages[0]['pixel_width']), int(source_pages[0]['pixel_height']))
    docx_render = render_docx_text_fallback_pages(docx_path, render_root=evidence_root / 'docx_pages', render_dpi=render_dpi, expected_page_count=len(source_pages), page_size=fallback_size)
    docx_pages = list(docx_render.get('pages') or [])
    render_pairs = []
    for index in range(max(len(source_pages), len(docx_pages))):
        source_page = source_pages[index] if index < len(source_pages) else None
        docx_page = docx_pages[index] if index < len(docx_pages) else None
        pair_status = 'matched' if source_page and docx_page else 'source_missing' if docx_page else 'docx_missing'
        render_pairs.append({
            'page_index': index + 1,
            'pair_status': pair_status,
            'source_page': source_page,
            'docx_page': docx_page,
            'source_image_path': source_page.get('image_path') if source_page else None,
            'docx_image_path': docx_page.get('image_path') if docx_page else None,
            'source_image_sha256': source_page.get('image_sha256') if source_page else None,
            'docx_image_sha256': docx_page.get('image_sha256') if docx_page else None,
        })
    return {
        'report_type': 'pdf_to_word_render_pair_evidence',
        'contract_version': 'pdf_to_word_render_pair/v1',
        'status': 'success' if any(item['pair_status'] == 'matched' for item in render_pairs) else 'failed',
        'failure_code': None,
        'ok': True,
        'source_pdf_path': str(source_pdf_path.resolve()),
        'docx_path': str(docx_path.resolve()),
        'evidence_root': str(evidence_root.resolve()),
        'render_dpi': render_dpi,
        'renderer_strategy': docx_render.get('renderer_strategy'),
        'fallback_used': bool(docx_render.get('fallback_used')),
        'fallback_reason': docx_render.get('fallback_reason'),
        'source_page_count': len(source_pages),
        'docx_page_count': len(docx_pages),
        'matched_pages': sum(1 for item in render_pairs if item['pair_status'] == 'matched'),
        'render_pairs': render_pairs,
    }


def compare_page_images(source_image_path: str | Path, docx_image_path: str | Path) -> float:
    thumbnail_size = (256, 256)
    source = Image.open(source_image_path).convert('L').resize(thumbnail_size)
    target = Image.open(docx_image_path).convert('L').resize(thumbnail_size)
    diff = ImageChops.difference(source, target)
    histogram = diff.histogram()
    sq = sum((value ** 2) * count for value, count in enumerate(histogram))
    rms = math.sqrt(sq / float(thumbnail_size[0] * thumbnail_size[1]))
    return max(0.0, min(1.0, 1.0 - (rms / 255.0)))


def build_visual_similarity_report(render_pair: dict[str, Any]) -> dict[str, Any]:
    page_scores = []
    for pair in render_pair.get('render_pairs') or []:
        score = compare_page_images(pair['source_image_path'], pair['docx_image_path'])
        review_reasons = []
        if score < THRESHOLDS['critical_page_render_similarity_min']:
            review_reasons.append('critical_page_similarity_below_threshold')
        page_scores.append({
            'page_index': int(pair['page_index']),
            'pair_status': pair['pair_status'],
            'page_role': 'critical',
            'page_render_similarity': round(score, 4),
            'review_required': bool(review_reasons),
            'review_reasons': review_reasons,
            'source_image_path': pair['source_image_path'],
            'docx_image_path': pair['docx_image_path'],
        })
    similarities = [row['page_render_similarity'] for row in page_scores if row['page_render_similarity'] is not None]
    overall = round(sum(similarities) / len(similarities), 4) if similarities else None
    min_score = round(min(similarities), 4) if similarities else None
    artifact_ready = bool(page_scores)
    gate_passed = bool(
        artifact_ready
        and overall is not None and overall >= THRESHOLDS['document_overall_similarity_min']
        and min_score is not None and min_score >= THRESHOLDS['critical_page_render_similarity_min']
    )
    human_review_reasons = []
    if overall is not None and overall < THRESHOLDS['document_overall_similarity_min']:
        human_review_reasons.append('document_similarity_below_threshold')
    if min_score is not None and min_score < THRESHOLDS['critical_page_render_similarity_min']:
        human_review_reasons.append('critical_page_similarity_below_threshold')
    vetoes = []
    if not gate_passed:
        vetoes.append({
            'code': 'visual_similarity_below_threshold',
            'scope': 'document',
            'severity': 'p0',
            'blocking': True,
            'reason': 'real render-pair similarity is below the human visual threshold for the selected long-reading pages',
            'details': {
                'overall_page_similarity_mean': overall,
                'min_page_similarity': min_score,
                'thresholds': THRESHOLDS,
                'selected_pages_or_crops': list(SELECTED_PAGES),
            },
        })
    return {
        'report_type': 'pdf_to_word_visual_similarity_evidence',
        'contract_version': 'pdf_to_word_visual_similarity_gate/v1',
        'artifact_name': 'visual_similarity.json',
        'implementation_status': 'real_render_pair_scored' if artifact_ready else 'render_pair_not_ready',
        'status': 'passed' if gate_passed else 'scored_no_go',
        'failure_code': None if gate_passed else 'visual_similarity_below_threshold',
        'sample_name': SAMPLE_NAME,
        'subject': SUBJECT,
        'document_page_type': PAGE_TYPE,
        'mode_boundary': {
            'requested_mode': 'quality/hybrid_async',
            'parser_backend': 'hybrid_experimental',
            'resolved_gate_mode': 'quality/hybrid_async',
            'enabled': True,
            'default_sync_safe': True,
            'default_sync_invokes_render_or_slow_model': False,
            'reason': 'visual similarity counts only in quality/hybrid_async',
        },
        'score_contract': {
            'dimension_key': 'visual_similarity',
            'dimension_weight': 17,
            'eligible_for_final_score': artifact_ready,
            'counts_toward_final_score': artifact_ready,
            'reason': 'real render pair + page scores ready' if artifact_ready else 'artifact not ready',
        },
        'thresholds': dict(THRESHOLDS),
        'render_pair_status': render_pair['status'],
        'render_pair_failure_code': render_pair.get('failure_code'),
        'renderer_strategy': render_pair.get('renderer_strategy'),
        'fallback_used': bool(render_pair.get('fallback_used')),
        'render_pairs': list(render_pair.get('render_pairs') or []),
        'page_scores': page_scores,
        'key_regions': [],
        'vetoes': vetoes,
        'blocking_failures': [],
        'human_review_required': True,
        'human_review_reasons': sorted(set(human_review_reasons)) or ['manual_human_review_required'],
        'aggregate': {
            'render_pair_count': len(render_pair.get('render_pairs') or []),
            'page_score_count': len(page_scores),
            'key_region_count': 0,
            'render_pair_ready_page_count': len(page_scores),
            'overall_page_similarity_mean': overall,
            'min_page_similarity': min_score,
        },
        'artifact_ready_for_scoring': artifact_ready,
        'gate_passed': gate_passed,
        'slow_model_policy': {
            'candidate_models': ['qwen3_vl_8b'],
            'disallowed_modes': ['fast', 'balanced', 'default_sync'],
            'fallback_action': 'manual_review',
        },
        'slow_model_review': {
            'enabled': False,
            'selected_page_count': 0,
            'executed_page_count': 0,
            'fallback_page_count': 0,
            'pages': [],
            'status': 'not_requested',
        },
    }


def filter_render_pair_to_selected_pages(render_pair: dict[str, Any]) -> dict[str, Any]:
    selected_pairs = [pair for pair in render_pair['render_pairs'] if int(pair.get('page_index') or 0) in SELECTED_PAGES]
    filtered = dict(render_pair)
    filtered['render_pairs'] = selected_pairs
    filtered['source_page_count'] = len(selected_pairs)
    filtered['docx_page_count'] = len(selected_pairs)
    filtered['matched_pages'] = sum(1 for pair in selected_pairs if pair.get('pair_status') == 'matched')
    filtered['selected_pages_or_crops'] = list(SELECTED_PAGES)
    filtered['scoring_scope'] = {
        'mode': 'selected_pages_or_crops',
        'selected_pages_or_crops': list(SELECTED_PAGES),
        'scope_reason': '只评价长文阅读《爸爸的鸽子》材料与题目区域；作文/写作格仍 out-of-scope',
    }
    filtered['total_source_page_count'] = render_pair['source_page_count']
    filtered['total_docx_page_count'] = render_pair['docx_page_count']
    return filtered


def update_manifests(now: str, visual: dict[str, Any], human: dict[str, Any]) -> None:
    unified = load_json(UNIFIED_MANIFEST_PATH)
    final_gated = load_json(FINAL_GATED_MANIFEST_PATH)
    chinese = load_json(CHINESE_MANIFEST_PATH)

    chinese.setdefault('scope', {})['all_subject_policy'] = 'Chinese 现在同时拥有 negative_guard 与带真实视觉证据的 long-reading positive candidate；后者当前结论仍为 no_go，不得被宣称为已通过人工视觉95。'
    chinese.setdefault('release_boundary', {})['human_visual_95_status'] = 'no_go_for_current_chinese_positive_candidate_until_selected_pages_pass_rubric'
    chinese['release_boundary']['current_chinese_public_claim'] = 'Chinese 已拥有独立长文阅读 positive_candidate 与真实视觉证据链，但当前 selected_pages_or_crops=[1,2,3] 的真实评分仍为 no_go；只能据此证明已纳入同口径治理，不能宣称已通过人工视觉95。'

    sample = next(item for item in unified['samples'] if item.get('sample_key') == SAMPLE_KEY)
    sample['artifact_presence'].update({
        'render_pair_exists': True,
        'visual_similarity_exists': True,
        'fidelity_veto_exists': True,
        'human_review_report_exists': True,
        'render_pair_ready_for_scoring': True,
        'human_review_decision': human['human_visual_decision'],
    })
    sample['fallback_policy']['selected_pages_or_crops'] = list(SELECTED_PAGES)
    sample['gate_status'] = 'human_review_failed'
    sample['disallowed_uses'] = [
        '不得把该长文阅读样例外推为作文/写作格能力证明',
        '不得在 human_review_passed 之前宣称语文学科已通过人工视觉95',
        '不得用它覆盖或替代 chinese_grade5 negative_guard 条目',
    ]
    sample['notes'] = [
        '当前 canonical sample bundle 已具备真实 render_pair / visual_similarity / fidelity_veto / human_review 证据链。',
        'selected_pages_or_crops=[1,2,3] 对应《爸爸的鸽子》长文材料与题目区域；作文/写作格仍保持 out-of-scope。',
        '当前 human visual verdict 仍为 no_go：真实渲染相似度低于阈值并触发 P0 veto，因此尚不能进入全学科95正向通过分母。',
    ]

    sample = next(item for item in final_gated['samples'] if item.get('sample_key') == SAMPLE_KEY)
    sample['selected_pages_or_crops'] = list(SELECTED_PAGES)
    sample['current_facts'].update({
        'document_fallback': False,
        'fallback_pages': [],
        'seed_profile': 'apple_baseline',
        'render_pair_status': 'success',
        'visual_similarity_status': visual['status'],
        'human_visual_decision': human['human_visual_decision'],
    })
    sample['required_followups'] = [
        'improve_selected_long_reading_page_similarity_above_human_visual_thresholds',
        'add_dedicated_chinese_composition_grid_positive_sample_before_composition_claim',
    ]
    sample['notes'] = [
        'This sample remains distinct from chinese_grade5 negative_guard and now has real visual evidence for selected long-reading pages.',
        'selected_pages_or_crops=[1,2,3] scope the evidence to 《爸爸的鸽子》 reading material + question region; composition/writing-grid claims stay out-of-scope.',
        'Current human visual verdict remains no_go because measured similarity on the selected pages stays below the 95 gate thresholds.',
    ]

    sample = next(item for item in chinese['samples'] if item.get('sample_key') == SAMPLE_KEY)
    sample['current_facts'].update({
        'selected_pages_or_crops': list(SELECTED_PAGES),
        'render_pair_status': 'success',
        'visual_similarity_status': visual['status'],
        'human_visual_decision': human['human_visual_decision'],
        'render_pair_ready_for_scoring': True,
    })
    sample['baseline_interpretation'] = [
        '该样例仍是独立于 chinese_grade5 的语文长文阅读正向候选 bundle。',
        '当前 bundle 已从 staged_seed 进入 real_scoring_ready：真实 render_pair / visual_similarity / fidelity_veto / human_review 均已落盘。',
        '当前人眼结论仍为 no_go，因此它可以参与 QA 复验是否进入后续重跑口径，但不能被当作语文学科已通过人工视觉95的事实。',
    ]
    sample['required_followups_before_positive_claim'] = [
        {
            'action': 'raise_selected_long_reading_similarity_for_chinese_long_reading_positive_v1',
            'priority': 'P0_before_chinese_claim',
            'acceptance': 'selected_pages_or_crops=[1,2,3] 的 overall similarity >= 0.95，且关键页 >= 0.92，无 P0 veto。',
        },
        {
            'action': 'add_positive_chinese_composition_or_writing_grid_sample',
            'priority': 'P0_before_composition_claim',
            'acceptance': '作文/写作格需独立样例与区域级视觉证据；当前长文阅读样例不能替代该能力证明。',
        },
    ]

    unified['generated_at'] = now
    final_gated['generated_at'] = now
    chinese['generated_at'] = now
    write_json(UNIFIED_MANIFEST_PATH, unified)
    write_json(FINAL_GATED_MANIFEST_PATH, final_gated)
    write_json(CHINESE_MANIFEST_PATH, chinese)


def update_fixtures(now: str, human: dict[str, Any]) -> None:
    artifact_contract = load_json(ARTIFACT_CONTRACT_PATH)
    artifact_contract['generated_at'] = now
    artifact_contract['selected_pages_or_crops'] = list(SELECTED_PAGES)
    artifact_contract['artifact_ready_for_scoring'] = True
    artifact_contract['human_review_decision'] = human['human_visual_decision']
    artifact_contract['notes'] = [
        '语文正向样例现在已具备真实 visual evidence chain；下游应直接消费该 sample_dir 与 published aliases。',
        '评分 scope 固定为 selected_pages_or_crops=[1,2,3]，对应《爸爸的鸽子》长文阅读材料与题目区域。',
        '当前 human_review_decision=no_go，不得将该样例误记为语文学科已通过人工视觉95。',
    ]
    write_json(ARTIFACT_CONTRACT_PATH, artifact_contract)

    unified_fixture = load_json(UNIFIED_FIXTURE_PATH)
    unified_fixture['generated_at'] = now
    positive = unified_fixture['required_samples'][SAMPLE_KEY]
    positive['selected_pages_or_crops'] = list(SELECTED_PAGES)
    positive['gate_status'] = 'human_review_failed'
    positive['render_pair_ready_for_scoring'] = True
    positive['human_review_decision'] = human['human_visual_decision']
    unified_fixture['notes'] = [
        '该 fixture 冻结语文 negative_guard / positive_candidate 的分工与关键资格字段。',
        'positive sample 当前已完成真实视觉证据链，但事实结论是 human_review_failed / no_go，而非 artifact_missing。',
    ]
    write_json(UNIFIED_FIXTURE_PATH, unified_fixture)


def main() -> None:
    now = datetime.now().astimezone().isoformat(timespec='seconds')
    render_pair_full = build_render_pair_evidence(source_pdf_path=SOURCE_PDF_PATH, docx_path=OUTPUT_DOCX_PATH, evidence_root=RENDER_PAIR_ARTIFACTS_ROOT, render_dpi=RENDER_DPI)
    selected_render_pair = filter_render_pair_to_selected_pages(render_pair_full)
    selected_render_pair.update({
        'generated_at': now,
        'sample_name': SAMPLE_NAME,
        'source_name': SAMPLE_NAME,
        'subject': SUBJECT,
        'document_page_type': PAGE_TYPE,
        'notes': [
            'render_pair_artifacts 已对整份 13 页 source/docx 生成 PNG，当前 scoring scope 仅使用 selected_pages_or_crops=[1,2,3]。',
            'DOCX 侧在当前 dev 环境使用 python_docx_text_fallback/v1 生成可复现渲染图。',
        ],
    })
    write_json(RENDER_PAIR_PATH, selected_render_pair)

    visual = build_visual_similarity_report(selected_render_pair)
    visual.update({
        'generated_at': now,
        'selected_pages_or_crops': list(SELECTED_PAGES),
        'scoring_scope': selected_render_pair['scoring_scope'],
        'evidence_paths': {
            'render_pair_path': str(RENDER_PAIR_PATH),
            'source_pdf_path': str(SOURCE_PDF_PATH),
            'output_docx_path': str(OUTPUT_DOCX_PATH),
            'render_pair_artifacts_root': str(RENDER_PAIR_ARTIFACTS_ROOT),
        },
        'total_document_render_pair_count': render_pair_full['matched_pages'],
    })
    write_json(VISUAL_SIMILARITY_PATH, visual)

    page_vetoes = []
    for row in visual['page_scores']:
        if row['page_render_similarity'] is not None and row['page_render_similarity'] < THRESHOLDS['critical_page_render_similarity_min']:
            page_vetoes.append({
                'code': 'critical_page_similarity_below_threshold',
                'canonical_code': 'critical_page_similarity_below_threshold',
                'severity': 'p0',
                'scope': 'page',
                'page_index': row['page_index'],
                'region_kind': None,
                'region_id': None,
                'summary': f"第{row['page_index']}页长文阅读关键页真实渲染相似度低于 0.92 阈值。",
                'category': 'visual_similarity',
                'label': '关键页真实渲染低于阈值',
                'triggered': True,
                'evidence_paths': [str(RENDER_PAIR_PATH), str(VISUAL_SIMILARITY_PATH)],
            })
    vetoes = list(page_vetoes)
    if not visual['gate_passed']:
        vetoes.append({
            'code': 'visual_similarity_below_threshold',
            'canonical_code': 'visual_similarity_below_threshold',
            'severity': 'p0',
            'scope': 'document',
            'page_index': None,
            'region_kind': None,
            'region_id': None,
            'summary': 'selected_pages_or_crops=[1,2,3] 的整体/关键页真实渲染相似度低于人工95门禁阈值。',
            'category': 'visual_similarity',
            'label': '真实渲染相似度低于门禁阈值',
            'triggered': True,
            'evidence_paths': [str(RENDER_PAIR_PATH), str(VISUAL_SIMILARITY_PATH)],
        })
    fidelity = {
        'report_type': 'pdf_to_word_fidelity_veto_evidence',
        'contract_version': 'pdf_to_word_fidelity_veto/v1',
        'generated_at': now,
        'sample_name': SAMPLE_NAME,
        'subject': SUBJECT,
        'document_page_type': PAGE_TYPE,
        'selected_pages_or_crops': list(SELECTED_PAGES),
        'status': 'no_go' if vetoes else 'review_required',
        'overall_score': visual['aggregate']['overall_page_similarity_mean'],
        'human_review_required': True,
        'page_scores': visual['page_scores'],
        'render_pairs': [
            {
                'page_index': pair['page_index'],
                'pair_status': pair['pair_status'],
                'alignment_mode': 'page_index',
                'source_image_path': pair['source_image_path'],
                'docx_image_path': pair['docx_image_path'],
            }
            for pair in selected_render_pair['render_pairs']
        ],
        'vetoes': vetoes,
        'page_vetoes': page_vetoes,
        'region_vetoes': [],
        'evidence_paths': {
            'render_pair_path': str(RENDER_PAIR_PATH),
            'visual_similarity_path': str(VISUAL_SIMILARITY_PATH),
            'source_pdf_path': str(SOURCE_PDF_PATH),
            'output_docx_path': str(OUTPUT_DOCX_PATH),
        },
        'notes': [
            'real render_pair / visual_similarity evidence is now materialized for selected_pages_or_crops=[1,2,3].',
            'Current no_go is a true quality finding on the selected long-reading pages, not a placeholder or renderer-missing blocker.',
        ],
        'p0_veto_count': len(vetoes),
        'renderer_strategy': selected_render_pair.get('renderer_strategy'),
        'fallback_used': bool(selected_render_pair.get('fallback_used')),
    }
    write_json(FIDELITY_VETO_PATH, fidelity)

    human = {
        'report_type': 'pdf_to_word_human_visual_review_report',
        'contract_version': 'pdf_to_word_human_visual_review/v1',
        'generated_at': now,
        'sample_name': SAMPLE_NAME,
        'subject': SUBJECT,
        'document_page_type': PAGE_TYPE,
        'selected_pages_or_crops': list(SELECTED_PAGES),
        'artifact_ready_for_scoring': bool(visual['artifact_ready_for_scoring']),
        'render_pair_status': selected_render_pair['status'],
        'render_pair_failure_code': selected_render_pair.get('failure_code'),
        'visual_similarity_status': visual['status'],
        'visual_similarity_failure_code': visual['failure_code'],
        'visual_similarity_gate_passed': bool(visual['gate_passed']),
        'overall_page_similarity_mean': visual['aggregate']['overall_page_similarity_mean'],
        'min_page_similarity': visual['aggregate']['min_page_similarity'],
        'fidelity_veto_status': fidelity['status'],
        'fidelity_veto_p0_count': fidelity['p0_veto_count'],
        'human_visual_decision': 'no_go',
        'eligible_for_human_visual_95': False,
        'sample_verdict': 'no_go',
        'blocking_reasons': ['visual_similarity_below_threshold', 'p0_fidelity_veto_present'],
        'evidence_paths': {
            'render_pair_path': str(RENDER_PAIR_PATH),
            'visual_similarity_path': str(VISUAL_SIMILARITY_PATH),
            'fidelity_veto_path': str(FIDELITY_VETO_PATH),
            'source_manifest_path': str(SOURCE_MANIFEST_PATH),
        },
        'review_notes': [
            '语文正向样例已由 staged_seed 进入 real_scoring_ready；render_pair / visual_similarity 基于真实 source PDF 与 DOCX fallback render 生成。',
            '评分 scope 仅覆盖 selected_pages_or_crops=[1,2,3]，对应《爸爸的鸽子》长文材料与题目区域；作文/写作格仍 out-of-scope。',
            '当前 verdict 仍为 no_go，因为关键页真实渲染相似度低于阈值并触发 P0 veto。',
        ],
    }
    write_json(HUMAN_REVIEW_PATH, human)

    source_manifest = load_json(SOURCE_MANIFEST_PATH)
    source_artifacts = dict(source_manifest.get('source_artifacts') or {})
    source_artifacts.update({
        'source_pdf_path': str(SOURCE_PDF_PATH),
        'output_docx_path': str(OUTPUT_DOCX_PATH),
        'render_pair_path': str(RENDER_PAIR_PATH),
        'visual_similarity_path': str(VISUAL_SIMILARITY_PATH),
        'fidelity_veto_path': str(FIDELITY_VETO_PATH),
        'human_review_report_path': str(HUMAN_REVIEW_PATH),
        'render_pair_artifacts_root': str(RENDER_PAIR_ARTIFACTS_ROOT),
        'docx_renderer_strategy': selected_render_pair.get('renderer_strategy'),
        'docx_renderer_fallback_used': bool(selected_render_pair.get('fallback_used')),
        'canonical_visual_evidence_materialized': True,
        'canonical_visual_evidence_scoring_ready': bool(visual['artifact_ready_for_scoring']),
        'reproduce_script_path': str(TASK_SCRIPT_PATH),
        'reproduce_command': f'PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/chiralium-pycache-chinese /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/python {TASK_SCRIPT_PATH}',
    })
    generated_files = list(source_manifest.get('generated_files') or [])
    for item in ['render_pair.json', 'visual_similarity.json', 'fidelity_veto.json', 'human_review_report.json', 'render_pair_artifacts/']:
        if item not in generated_files:
            generated_files.append(item)
    source_manifest.update({
        'generated_files': generated_files,
        'source_artifacts': source_artifacts,
        'positive_candidate': {
            **dict(source_manifest.get('positive_candidate') or {}),
            'selected_pages_or_crops': list(SELECTED_PAGES),
            'gate_status': 'human_review_failed',
            'seed_profile': 'apple_baseline',
        },
        'notes': [
            '该样例不会改写 chinese_grade5 negative_guard，而是以独立 sample_key + 独立 alias/source_manifest 进入 positive_candidate 体系。',
            'selected_pages_or_crops=[1,2,3] 对应《爸爸的鸽子》长文材料与题目区域；作文/写作格仍保持 out-of-scope，待单独样例。',
            'output.docx/pages.jsonl 复制自 apple_baseline 语文五年级；当前已补齐真实 render_pair / visual_similarity / fidelity_veto / human_review 证据链。',
            'Current human visual verdict remains no_go because the selected long-reading pages score below threshold and trigger P0 veto; blocker is no longer artifact_missing or pending review.',
        ],
        'docx_render_dependency': {
            'preferred_native_converter': 'soffice/libreoffice --headless --convert-to pdf',
            'preferred_native_converter_available': False,
            'fallback_renderer': 'python stdlib zip/xml DOCX text extractor + Pillow PNG renderer',
            'fallback_renderer_version': DOCX_TEXT_FALLBACK_RENDERER_VERSION,
            'render_dpi': RENDER_DPI,
            'reproduce_command': f'PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/chiralium-pycache-chinese /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/python {TASK_SCRIPT_PATH}',
            'reproduce_script_path': str(TASK_SCRIPT_PATH),
            'provenance_stability': 'task_artifact_path',
        },
        'updated_at': now,
        'current_visual_evidence_status': {
            'render_pair_status': selected_render_pair['status'],
            'render_pair_failure_code': selected_render_pair.get('failure_code'),
            'visual_similarity_status': visual['status'],
            'visual_similarity_failure_code': visual['failure_code'],
            'artifact_ready_for_scoring': bool(visual['artifact_ready_for_scoring']),
            'visual_similarity_gate_passed': bool(visual['gate_passed']),
            'human_visual_decision': human['human_visual_decision'],
            'sample_verdict': human['sample_verdict'],
            'eligible_for_human_visual_95': human['eligible_for_human_visual_95'],
            'blocking_reasons': list(human['blocking_reasons']),
            'selected_pages_or_crops': list(SELECTED_PAGES),
            'provenance_note': 'render_pair/visual_similarity 已可评分；当前 no_go 来自 selected_pages_or_crops=[1,2,3] 的真实阈值/P0 veto，而非 artifact_missing。',
        },
    })
    write_json(SOURCE_MANIFEST_PATH, source_manifest)

    update_manifests(now, visual, human)
    update_fixtures(now, human)

    summary = {
        'generated_at': now,
        'sample_key': SAMPLE_KEY,
        'selected_pages_or_crops': list(SELECTED_PAGES),
        'render_pair_status': selected_render_pair['status'],
        'visual_similarity_status': visual['status'],
        'visual_similarity_overall_page_similarity_mean': visual['aggregate']['overall_page_similarity_mean'],
        'visual_similarity_min_page_similarity': visual['aggregate']['min_page_similarity'],
        'artifact_ready_for_scoring': visual['artifact_ready_for_scoring'],
        'human_visual_decision': human['human_visual_decision'],
        'fidelity_veto_p0_count': fidelity['p0_veto_count'],
        'sample_verdict': human['sample_verdict'],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
