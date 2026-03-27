"""
Quick smoke test for the MTG Judge API.

Usage:
    python scripts/test_local.py                          # test against localhost
    python scripts/test_local.py https://mtg-judge.fly.dev  # test against deployed server

Requires: pip install httpx
"""

import sys
import json
import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"


def test_health():
    print(f"Testing health endpoint at {BASE_URL}/health ...")
    r = httpx.get(f"{BASE_URL}/health", timeout=10)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert r.json() == {"status": "ok"}, f"Unexpected response: {r.json()}"
    print("  Health check passed!\n")


def test_validation():
    print("Testing validation (missing api_key) ...")
    payload = {
        "question": "test",
        "board_state": {},
        "life_totals": {},
        "active_player": "player1",
    }
    r = httpx.post(f"{BASE_URL}/judge", json=payload, timeout=10)
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"
    print("  Validation test passed!\n")


def test_judge_request(api_key: str | None = None):
    if not api_key:
        print("Skipping live judge test (no API key provided).")
        print("  To test: python scripts/test_local.py <base_url> <api_key>\n")
        return

    print("Testing judge endpoint with live API key ...")
    payload = {
        "question": "Can [[Lightning Bolt]] target a planeswalker?",
        "board_state": {
            "player1": {
                "battlefield": ["Lightning Bolt"],
                "graveyard": [],
                "exile": [],
                "hand_count": 6,
            },
            "player2": {
                "battlefield": ["Jace, the Mind Sculptor"],
                "graveyard": [],
                "exile": [],
                "hand_count": 7,
            },
        },
        "life_totals": {"player1": 20, "player2": 20},
        "active_player": "player1",
        "api_key": api_key,
        "session_id": "test_player",
    }
    r = httpx.post(f"{BASE_URL}/judge", json=payload, timeout=30)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    print(json.dumps(data, indent=2))
    print("  Judge request passed!\n")


if __name__ == "__main__":
    api_key = sys.argv[2] if len(sys.argv) > 2 else None

    test_health()
    test_validation()
    test_judge_request(api_key)

    print("All smoke tests passed!")
