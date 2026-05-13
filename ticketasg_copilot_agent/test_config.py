"""
Tests for ticketasg_copilot_agent/config.py.

Behaviours tested:
  - load_config() with no .env returns ServiceNowConfig with assignment_rules_file
    ending in "assignment_rules.json"
  - load_config() respects ASSIGNMENT_RULES_FILE env var
  - SmtpConfig.enabled is False when SMTP_HOST is empty
"""
import os
import sys
import pathlib
import importlib

# Ensure the package directory is on the path so config.py can be imported
_PKG = pathlib.Path(__file__).resolve().parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))


def _reload_config():
    """Re-import config fresh (avoids cached module state between tests)."""
    if "config" in sys.modules:
        del sys.modules["config"]
    import config as cfg_module
    return cfg_module


def test_assignment_rules_file_default_ends_with_json():
    cfg_module = _reload_config()
    cfg = cfg_module.load_config()
    assert hasattr(cfg, "assignment_rules_file"), (
        "ServiceNowConfig must have an 'assignment_rules_file' attribute"
    )
    assert cfg.assignment_rules_file.endswith("assignment_rules.json"), (
        f"Default assignment_rules_file should end with 'assignment_rules.json', got: {cfg.assignment_rules_file}"
    )


def test_assignment_rules_file_env_override():
    cfg_module = _reload_config()
    os.environ["ASSIGNMENT_RULES_FILE"] = "/tmp/custom_rules.json"
    try:
        cfg = cfg_module.load_config()
        assert cfg.assignment_rules_file == "/tmp/custom_rules.json", (
            f"Expected '/tmp/custom_rules.json' from env var, got: {cfg.assignment_rules_file}"
        )
    finally:
        del os.environ["ASSIGNMENT_RULES_FILE"]


def test_smtp_enabled_false_when_host_empty():
    cfg_module = _reload_config()
    # Build a SmtpConfig directly with empty host — ensures enabled=False regardless of .env
    smtp = cfg_module.SmtpConfig(
        host="",
        port=587,
        user="",
        password="",
        from_addr="",
        to_addrs=[],
        use_tls=True,
        verify_ssl=True,
    )
    assert smtp.enabled is False, (
        f"SmtpConfig.enabled should be False when host is empty, got: {smtp.enabled}"
    )


if __name__ == "__main__":
    test_assignment_rules_file_default_ends_with_json()
    print("PASS: test_assignment_rules_file_default_ends_with_json")
    test_assignment_rules_file_env_override()
    print("PASS: test_assignment_rules_file_env_override")
    test_smtp_enabled_false_when_host_empty()
    print("PASS: test_smtp_enabled_false_when_host_empty")
    print("ALL TESTS PASSED")
