from datetime import datetime, timezone

from capabilities.capabilities import CapabilityService
from capabilities.repository.clock import Clock
from config.config import config
from schemas.capability_schemas import GetPolicyGuidanceInput

REQ = GetPolicyGuidanceInput(sku="AC-001", warehouse_id="DEL-01", target_cover_days=14)


def _service(policy_path):
    return CapabilityService(
        repository=None,   # policy reads a file, not the DB
        clock=Clock(as_of=datetime(2026, 8, 30, 9, 0, tzinfo=timezone.utc)),
        config=config.model_copy(update={"policy_path": str(policy_path)}),
    )


def test_policy_ok(tmp_path):
    p = tmp_path / "policy.md"
    p.write_text("---\nversion: 2026-08-30\nsummary: Be conservative.\n---\nBody text.",
                 encoding="utf-8")
    result = _service(p).get_policy_guidance(REQ)

    assert result.success is True
    assert result.result_code == "OK"
    assert result.payload.policy_version == "2026-08-30"
    assert result.payload.summary == "Be conservative."
    assert result.payload.full_text == "Body text."
    assert len(result.evidence) == 1
    assert result.evidence[0].source == "policy"


def test_policy_not_found(tmp_path):
    result = _service(tmp_path / "missing.md").get_policy_guidance(REQ)
    assert result.success is False
    assert result.result_code == "NOT_FOUND"
    assert result.payload is None


def test_policy_no_frontmatter(tmp_path):
    p = tmp_path / "policy.md"
    p.write_text("# Just markdown, no header", encoding="utf-8")
    result = _service(p).get_policy_guidance(REQ)
    assert result.success is False
    assert result.result_code == "INVALID_DATA"


def test_policy_missing_keys(tmp_path):
    p = tmp_path / "policy.md"
    p.write_text("---\nversion: 2026-08-30\n---\nBody", encoding="utf-8")  # no summary
    result = _service(p).get_policy_guidance(REQ)
    assert result.success is False
    assert result.result_code == "INVALID_DATA"

def test_policy_malformed_yaml(tmp_path):
    p = tmp_path / "policy.md"
    p.write_text("---\nversion: [unclosed\n---\nBody", encoding="utf-8")  # invalid YAML
    result = _service(p).get_policy_guidance(REQ)
    assert result.success is False
    assert result.result_code == "INVALID_DATA"
