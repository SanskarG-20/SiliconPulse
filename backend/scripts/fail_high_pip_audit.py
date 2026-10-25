"""Fail pip-audit findings with CVSS >= 7.0 using OSV's published vectors."""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

import requests


def _score(vulnerability_id: str) -> float | None:
    from cvss import CVSS3, CVSS4

    response = requests.get(f"https://api.osv.dev/v1/vulns/{quote(vulnerability_id, safe='')}", timeout=15)
    response.raise_for_status()
    for severity in response.json().get("severity", []):
        vector = severity.get("score", "")
        try:
            if vector.startswith("CVSS:3"):
                return float(CVSS3(vector).scores()[0])
            if vector.startswith("CVSS:4"):
                return float(CVSS4(vector).scores()[0])
        except (ValueError, TypeError):
            continue
    return None


def main(path: str) -> int:
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    vulnerabilities = [v for dep in report.get("dependencies", []) for v in dep.get("vulns", [])]
    ids = list(dict.fromkeys(v["id"] for v in vulnerabilities))
    # Warm OSV in parallel, then score locally for predictable CVSS handling.
    with ThreadPoolExecutor(max_workers=8) as pool:
        scores = dict(zip(ids, pool.map(_score, ids)))
    highs = high_findings_from_scores(report, scores)
    for package, vulnerability_id, score in highs:
        print(f"HIGH CVSS {score:.1f}: {package} {vulnerability_id}")
    print(f"pip-audit findings: {len(vulnerabilities)}; high severity: {len(highs)}")
    return 1 if highs else 0


def high_findings_from_scores(report: dict, scores: dict[str, float | None]) -> list[tuple[str, str, float]]:
    highs = []
    for dep in report.get("dependencies", []):
        for vuln in dep.get("vulns", []):
            score = scores.get(vuln["id"])
            if score is not None and score >= 7.0:
                highs.append((dep["name"], vuln["id"], score))
    return highs


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
