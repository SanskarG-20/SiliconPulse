import os
import requests
import time

BASE_URL = os.getenv("SILICONPULSE_API_URL", "http://localhost:8000/api").rstrip("/")
AUTH_TOKEN = os.getenv("SILICONPULSE_AUTH_TOKEN", "").strip()
TIMEOUT_SECONDS = 8


def _headers():
    if not AUTH_TOKEN:
        return {}
    return {"Authorization": f"Bearer {AUTH_TOKEN}"}


def _request(method: str, path: str, **kwargs):
    return requests.request(
        method,
        f"{BASE_URL}{path}",
        headers=_headers(),
        timeout=TIMEOUT_SECONDS,
        **kwargs,
    )


def test_pathway_flow():
    print("Starting Pathway Integration Test...")

    print("Checking initial signals...")
    try:
        resp = _request("GET", "/signals")
        if resp.status_code == 401:
            print("Backend requires auth. Set SILICONPULSE_AUTH_TOKEN and rerun this test.")
            return
        resp.raise_for_status()
        initial_count = len(resp.json()) if isinstance(resp.json(), list) else 0
        print(f"Received {initial_count} initial signals")
    except Exception as exc:
        print(f"Failed to connect to backend: {exc}")
        return

    test_id = int(time.time())
    test_title = f"PATHWAY_TEST_SIGNAL_{test_id}"
    test_content = "Pathway pipeline verification signal. Keywords: NVIDIA, TSMC, contract."

    print(f"Injecting test signal: {test_title}")
    payload = {
        "title": test_title,
        "content": test_content,
        "source": "PathwayTester",
    }

    try:
        resp = _request("POST", "/inject", json=payload)
    except Exception as exc:
        print(f"Injection request failed: {exc}")
        return

    if resp.status_code == 200:
        print("Signal injected successfully")
    else:
        print(f"Injection failed [{resp.status_code}]: {resp.text[:300]}")
        return

    print("Waiting 5 seconds for Pathway processing...")
    time.sleep(5)

    print("Verifying signal in feed...")
    try:
        resp = _request("GET", "/signals")
        resp.raise_for_status()
        signals = resp.json()
    except Exception as exc:
        print(f"Signal verification request failed: {exc}")
        return

    if not isinstance(signals, list):
        print("FAILED: /signals returned a malformed non-list response.")
        return

    for signal in signals:
        if signal.get("title") == test_title:
            print("SUCCESS: Found processed signal in feed.")
            print(f"   - Company: {signal.get('company')}")
            print(f"   - Event Type: {signal.get('event_type')}")
            return

    print("FAILED: Injected signal not found in feed after processing window.")
    print("Check that pathway_pipeline.py is running and writing to data/pathway_out.jsonl.")


if __name__ == "__main__":
    test_pathway_flow()
