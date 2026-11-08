from actions.project_status import TOOL, project_status
from core.action_loader import _validate


def test_project_status_tool_schema():
    assert TOOL["name"] == "project_status"
    assert "project" in TOOL["description"].lower()
    assert callable(TOOL["handler"])

    rec = _validate(TOOL, "project_status.py")
    assert rec.valid is True
    assert rec.name == "project_status"


def test_project_status_execution(tmp_path):
    result = project_status({"detail": "full"})
    assert result.status == "success"
    assert isinstance(result.summary, str)
    assert isinstance(result.data, dict)
    assert "active_project" in result.data
    assert "sources" in result.data
    assert isinstance(result.evidence, list)

    # Check evidence structure
    for ev in result.evidence:
        assert "source" in ev
        assert "confidence" in ev
