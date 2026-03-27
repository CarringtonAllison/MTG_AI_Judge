import pytest
import time
from unittest.mock import patch
from services.session import get_history, add_exchange, clear_session, cleanup_expired, _sessions


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear session store before each test."""
    _sessions.clear()
    yield
    _sessions.clear()


class TestSessionStore:
    def test_create_session(self):
        """New session_id returns empty history."""
        history = get_history("player_white")
        assert history == []

    def test_add_exchange(self):
        """Adding a Q&A pair stores it in session."""
        add_exchange("player_white", "Can I bolt a walker?", "Yes you can.")
        history = get_history("player_white")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Can I bolt a walker?"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Yes you can."

    def test_get_history(self):
        """Retrieves full conversation history as role/content dicts."""
        add_exchange("p1", "Q1", "A1")
        add_exchange("p1", "Q2", "A2")
        history = get_history("p1")
        assert len(history) == 4
        assert history[0] == {"role": "user", "content": "Q1"}
        assert history[1] == {"role": "assistant", "content": "A1"}
        assert history[2] == {"role": "user", "content": "Q2"}
        assert history[3] == {"role": "assistant", "content": "A2"}

    def test_history_max_length(self):
        """After 5 exchanges, oldest is dropped (rolling window)."""
        for i in range(6):
            add_exchange("p1", f"Q{i}", f"A{i}")
        history = get_history("p1")
        # 5 exchanges max = 10 messages
        assert len(history) == 10
        # Oldest (Q0/A0) should be gone, Q1 should be first
        assert history[0]["content"] == "Q1"

    def test_session_ttl_expiry(self):
        """Session older than 15 minutes returns empty history."""
        add_exchange("p1", "Q", "A")
        # Patch the last_active timestamp to 16 minutes ago
        _sessions["p1"]["last_active"] = time.time() - 960
        history = get_history("p1")
        assert history == []

    def test_clear_session(self):
        """Explicitly clearing a session removes all history."""
        add_exchange("p1", "Q", "A")
        clear_session("p1")
        history = get_history("p1")
        assert history == []

    def test_independent_sessions(self):
        """Two different session_ids maintain separate histories."""
        add_exchange("white", "Q1", "A1")
        add_exchange("blue", "Q2", "A2")
        white_history = get_history("white")
        blue_history = get_history("blue")
        assert len(white_history) == 2
        assert len(blue_history) == 2
        assert white_history[0]["content"] == "Q1"
        assert blue_history[0]["content"] == "Q2"

    def test_empty_session_id_skips_storage(self):
        """Empty string session_id means no session tracking."""
        add_exchange("", "Q", "A")
        history = get_history("")
        assert history == []
        assert "" not in _sessions
