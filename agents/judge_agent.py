import json
import anthropic
from models.schemas import JudgeRequest, JudgeResponse, ScryfallCard, RulesChunk

SYSTEM_PROMPT = """You are a certified Level 2 Magic: The Gathering judge. Your role is to provide accurate rulings based on the MTG Comprehensive Rules.

INSTRUCTIONS:
1. Analyze the question, board state, and relevant card text provided.
2. Cite specific rule numbers (e.g., "Rule 702.2a") to support your answer.
3. Consider the current board state, active player, and game context.
4. Explain in clear, plain language that any player can understand.
5. NEVER invent or fabricate rules. If you are unsure, say so.
6. If the context is insufficient to give a definitive ruling, flag this clearly.
7. Consider interactions between multiple cards if relevant.
8. If web sources are provided, use them as supplementary context but always prefer official rules.

You MUST respond with a JSON object in this exact format:
{
    "ruling": "Direct answer to the question (1-2 sentences)",
    "explanation": "Detailed explanation with rule citations",
    "rules_cited": ["rule_number_1", "rule_number_2"],
    "cards_referenced": ["Card Name 1", "Card Name 2"]
}

Respond ONLY with the JSON object, no other text."""


def build_prompt(request: JudgeRequest, context: dict) -> str:
    """Build the user prompt from the request and gathered context."""
    parts = []

    # Question
    parts.append(f"## QUESTION\n{request.question}")

    # Active player
    parts.append(f"\n## ACTIVE PLAYER\n{request.active_player}")

    # Board state
    if request.board_state:
        parts.append("\n## BOARD STATE")
        for player_name, state in request.board_state.items():
            life = request.life_totals.get(player_name, "unknown")
            parts.append(f"\n### {player_name} (Life: {life})")
            if hasattr(state, "battlefield"):
                parts.append(f"Battlefield: {', '.join(state.battlefield) if state.battlefield else 'empty'}")
                parts.append(f"Graveyard: {', '.join(state.graveyard) if state.graveyard else 'empty'}")
                parts.append(f"Exile: {', '.join(state.exile) if state.exile else 'empty'}")
                parts.append(f"Cards in hand: {state.hand_count}")

    # Card data
    cards: list[ScryfallCard] = context.get("cards", [])
    if cards:
        parts.append("\n## CARD DATA")
        for card in cards:
            parts.append(f"\n### {card.name}")
            parts.append(f"Type: {card.type_line}")
            parts.append(f"Mana Cost: {card.mana_cost}")
            parts.append(f"Oracle Text: {card.oracle_text}")
            if card.keywords:
                parts.append(f"Keywords: {', '.join(card.keywords)}")

    # Rules
    rules: list[RulesChunk] = context.get("rules", [])
    if rules:
        parts.append("\n## RELEVANT RULES")
        for rule in rules:
            parts.append(f"\nRule {rule.rule_number}: {rule.rule_text}")

    # Web sources (fallback)
    web_results = context.get("web_results", [])
    if web_results:
        parts.append("\n## WEB SOURCES (supplementary — prefer official rules)")
        for result in web_results:
            parts.append(f"\n### {result.get('title', 'Untitled')}")
            parts.append(f"Source: {result.get('url', '')}")
            parts.append(f"{result.get('snippet', '')}")

    return "\n".join(parts)


def build_messages(
    request: JudgeRequest,
    context: dict,
    session_history: list[dict] | None = None,
) -> list[dict]:
    """Build the Claude messages array with optional session history."""
    messages = []

    # Prepend session history if provided
    if session_history:
        messages.extend(session_history)

    # Append current question with full context
    prompt = build_prompt(request, context)
    messages.append({"role": "user", "content": prompt})

    return messages


async def get_ruling(
    request: JudgeRequest,
    context: dict,
    session_history: list[dict] | None = None,
) -> JudgeResponse:
    """Call Claude API to produce a ruling."""
    messages = build_messages(request, context, session_history)

    try:
        client = anthropic.AsyncAnthropic(api_key=request.api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages,
        )

        raw_text = response.content[0].text

        try:
            data = json.loads(raw_text)
            return JudgeResponse(
                ruling=data.get("ruling", ""),
                explanation=data.get("explanation", ""),
                rules_cited=data.get("rules_cited", []),
                cards_referenced=data.get("cards_referenced", []),
                web_sources=[r.get("url", "") for r in context.get("web_results", []) if r.get("url")],
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            return JudgeResponse(
                ruling=raw_text[:500],
                explanation="Response was not in expected JSON format.",
                rules_cited=[],
                cards_referenced=[],
            )

    except Exception as e:
        return JudgeResponse(
            ruling=f"Error: Unable to get ruling. {str(e)[:200]}",
            explanation="The judge service encountered an error.",
            rules_cited=[],
            cards_referenced=[],
        )
