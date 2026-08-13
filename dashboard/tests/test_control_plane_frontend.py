from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_control_plane_view_surfaces_real_delivery_evidence_and_empty_states():
    html = (ROOT / "dashboard/templates/index.html").read_text(encoding="utf-8")
    script = (ROOT / "dashboard/static/js/dashboard.js").read_text(encoding="utf-8")
    assert 'id="control-plane"' in html
    assert 'id="control-plane-evidence-table"' in html
    assert "payload.artifacts" in script
    assert "payload.gates" in script
    assert "payload.timelines" in script
    assert "payload.delivery" in script
    assert "暂无交付证据" in script
