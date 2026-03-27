import re
from models.schemas import JudgeRequest, ScryfallCard, RulesChunk, PlayerBoardState
from services.scryfall import get_cards
from services.rules_db import search_by_keywords
from services.web_search import fallback_search

KEYWORD_ABILITIES = [
    "deathtouch", "defender", "double strike", "enchant", "equip",
    "first strike", "flash", "flying", "haste", "hexproof",
    "indestructible", "lifelink", "menace", "protection", "prowess",
    "reach", "shroud", "trample", "vigilance", "ward",
]

GAME_CONCEPTS = [
    "stack", "priority", "combat", "damage", "mana", "cost",
    "target", "counter", "sacrifice", "destroy", "exile", "token",
    "copy", "triggered", "activated", "state-based", "replacement",
    "commander", "infect", "poison", "energy", "planeswalker",
]

BRACKET_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")

DB_PATH = "data/rules.db"
MIN_RULES_FOR_NO_FALLBACK = 2


def extract_card_names(
    question: str,
    board_state: dict[str, PlayerBoardState],
) -> list[str]:
    """Extract unique card names from question brackets and board state zones."""
    names: list[str] = []
    seen: set[str] = set()

    # 1. Extract from [[brackets]]
    for match in BRACKET_PATTERN.finditer(question):
        name = match.group(1).strip()
        if name and name not in seen:
            names.append(name)
            seen.add(name)

    # 2. Extract from board state zones
    for player_state in board_state.values():
        if isinstance(player_state, dict):
            player_state = PlayerBoardState(**player_state)
        for zone in [player_state.battlefield, player_state.graveyard, player_state.exile]:
            for card_name in zone:
                if card_name and card_name not in seen:
                    names.append(card_name)
                    seen.add(card_name)

    return names


def _extract_search_keywords(
    question: str,
    cards: list[ScryfallCard],
) -> list[str]:
    """Derive keywords for rules search from question text and card data."""
    combined_text = question.lower()
    for card in cards:
        combined_text += " " + card.oracle_text.lower()
        combined_text += " " + " ".join(k.lower() for k in card.keywords)

    found = []
    for kw in KEYWORD_ABILITIES + GAME_CONCEPTS:
        if kw in combined_text:
            found.append(kw)
    return found


async def build_context(
    request: JudgeRequest,
    db_path: str = DB_PATH,
) -> dict:
    """Build the full context for the judge agent.

    Steps:
    1. Extract card names from question + board state
    2. Fetch card data from Scryfall
    3. Derive search keywords from question + card oracle text
    4. Search rules DB for relevant rules
    5. If rules insufficient, trigger web search fallback
    """
    # Step 1
    card_names = extract_card_names(request.question, request.board_state)

    # Step 2
    cards = await get_cards(card_names) if card_names else []

    # Step 3
    search_keywords = _extract_search_keywords(request.question, cards)

    # Step 4
    rules = search_by_keywords(db_path, search_keywords) if search_keywords else []

    # Step 5 - web fallback if rules are insufficient
    web_results = []
    if len(rules) < MIN_RULES_FOR_NO_FALLBACK:
        web_results = await fallback_search(request.question)

    return {
        "cards": cards,
        "rules": rules,
        "card_names": card_names,
        "web_results": web_results,
    }
