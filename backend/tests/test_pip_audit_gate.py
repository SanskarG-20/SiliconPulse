from scripts.fail_high_pip_audit import high_findings_from_scores


def test_pip_audit_gate_fails_only_high_severity():
    report = {"dependencies": [{"name": "demo", "vulns": [{"id": "HIGH"}, {"id": "LOW"}, {"id": "UNKNOWN"}]}]}
    assert high_findings_from_scores(report, {"HIGH": 8.1, "LOW": 4.0, "UNKNOWN": None}) == [("demo", "HIGH", 8.1)]
