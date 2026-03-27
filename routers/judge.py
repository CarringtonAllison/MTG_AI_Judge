from fastapi import APIRouter
from models.schemas import JudgeRequest, JudgeResponse
from agents.context_agent import build_context
from agents.judge_agent import get_ruling
from services.session import get_history, add_exchange, cleanup_expired

router = APIRouter()


@router.post("/judge", response_model=JudgeResponse)
async def judge_question(request: JudgeRequest) -> JudgeResponse:
    """Main judge endpoint. Orchestrates context gathering, ruling, and session management."""
    # 1. Clean up expired sessions
    cleanup_expired()

    # 2. Get conversation history for this session
    history = get_history(request.session_id)

    # 3. Build context (cards, rules, web fallback if needed)
    context = await build_context(request)

    # 4. Get ruling from Claude (with session history for follow-ups)
    ruling = await get_ruling(request, context, session_history=history)

    # 5. Store this exchange in session for future follow-ups
    if request.session_id:
        add_exchange(request.session_id, request.question, ruling.ruling)

    # 6. Echo session_id back
    ruling.session_id = request.session_id
    return ruling
