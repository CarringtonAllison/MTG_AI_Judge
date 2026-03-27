import time

SESSION_TTL = 900  # 15 minutes in seconds
MAX_HISTORY = 5    # max Q&A exchanges per session (10 messages)

# In-memory store: {session_id: {"history": [...], "last_active": timestamp}}
_sessions: dict[str, dict] = {}


def get_history(session_id: str) -> list[dict]:
    """Return conversation history for session_id.

    Returns empty list if session_id is empty, session doesn't exist, or session expired.
    """
    if not session_id:
        return []

    session = _sessions.get(session_id)
    if session is None:
        return []

    # Check TTL expiry
    if time.time() - session["last_active"] > SESSION_TTL:
        del _sessions[session_id]
        return []

    return list(session["history"])


def add_exchange(session_id: str, question: str, answer: str) -> None:
    """Store a Q&A exchange in the session. No-op if session_id is empty."""
    if not session_id:
        return

    if session_id not in _sessions:
        _sessions[session_id] = {"history": [], "last_active": time.time()}

    session = _sessions[session_id]
    session["history"].append({"role": "user", "content": question})
    session["history"].append({"role": "assistant", "content": answer})
    session["last_active"] = time.time()

    # Trim to MAX_HISTORY exchanges (each exchange = 2 messages)
    max_messages = MAX_HISTORY * 2
    if len(session["history"]) > max_messages:
        session["history"] = session["history"][-max_messages:]


def clear_session(session_id: str) -> None:
    """Remove session from store."""
    _sessions.pop(session_id, None)


def cleanup_expired() -> int:
    """Remove all expired sessions. Returns count removed."""
    now = time.time()
    expired = [
        sid for sid, data in _sessions.items()
        if now - data["last_active"] > SESSION_TTL
    ]
    for sid in expired:
        del _sessions[sid]
    return len(expired)
