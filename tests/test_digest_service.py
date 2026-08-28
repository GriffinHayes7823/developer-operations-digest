from devtools_digest.digest_service import DigestRequest, decide_digest


def test_failed_build_makes_digest_sendable_and_omits_routine_success() -> None:
    request = DigestRequest.model_validate(
        {
            "recipient": "maintainers@example.com",
            "week": "2026-W35",
            "builds": [
                {"project": "cli", "status": "passed"},
                {"project": "python-sdk", "status": "failed"},
            ],
            "releases": [{"package": "deployctl", "version": "2.4.0"}],
            "diagnostics": [
                {"component": "artifact-signing", "message": "key rotation due", "severity": "warning"}
            ],
        }
    )

    decision = decide_digest(request)

    assert decision.action == "send"
    assert decision.subject == "Developer operations digest - 2026-W35"
    assert decision.lines == [
        "Release: deployctl 2.4.0",
        "Build failed: python-sdk",
        "Diagnostic (warning): artifact-signing - key rotation due",
    ]


def test_routine_success_only_skips_digest() -> None:
    request = DigestRequest.model_validate(
        {
            "recipient": "maintainers@example.com",
            "week": "2026-W35",
            "builds": [{"project": "cli", "status": "passed"}],
        }
    )

    assert decide_digest(request).action == "skip"
