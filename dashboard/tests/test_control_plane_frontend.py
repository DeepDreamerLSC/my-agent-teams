from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_control_plane_view_surfaces_real_delivery_evidence_and_empty_states():
    html = (ROOT / "dashboard/templates/index.html").read_text(encoding="utf-8")
    script = (ROOT / "dashboard/static/js/dashboard.js").read_text(encoding="utf-8")
    assert 'id="control-plane"' in html
    assert 'id="control-plane-evidence-table"' in html
    assert "payload.artifacts" in script
    assert "payload.quality" in script
    assert "qualityState.passed" in script
    assert "payload.gates" in script
    assert "payload.timelines" in script
    assert "payload.delivery" in script
    assert "暂无交付证据" in script


def test_collaboration_board_has_reconnect_redaction_and_delegated_authorization_ui():
    html = (ROOT / "dashboard/templates/index.html").read_text(encoding="utf-8")
    script = (ROOT / "dashboard/static/js/collaboration.js").read_text(encoding="utf-8")
    assert 'id="collaboration"' in html
    assert 'id="collab-topology"' in html
    assert 'id="collab-timeline"' in html
    assert 'id="collab-auth-body"' in html
    assert "EventSource" in script
    assert "/event-log" in script
    assert "after_event_id" in script
    assert "knownEventIds" in script
    assert "payload.privacy?.projection" in script
    assert "L1_REVIEWER_COORDINATOR" in script
    assert "L2_OWNER" in script
    assert "完整正文" in html
