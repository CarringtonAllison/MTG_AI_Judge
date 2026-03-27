import asyncio
from typing import Optional
import httpx
from models.schemas import ScryfallCard


SCRYFALL_BASE = "https://api.scryfall.com"
RATE_LIMIT_DELAY = 0.075  # 75ms between requests per Scryfall guidelines


class ScryfallError(Exception):
    """Raised on non-404 HTTP errors or timeouts from Scryfall."""
    pass


async def get_card(
    name: str,
    client: Optional[httpx.AsyncClient] = None,
) -> Optional[ScryfallCard]:
    """Fetch a single card from Scryfall by fuzzy name match.

    Returns ScryfallCard if found, None if 404.
    Raises ScryfallError on server errors or timeouts.
    """
    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=10.0)
        should_close = True

    try:
        response = await client.get(
            f"{SCRYFALL_BASE}/cards/named",
            params={"fuzzy": name},
        )

        if response.status_code == 404:
            return None

        if response.status_code != 200:
            raise ScryfallError(
                f"Scryfall returned {response.status_code} for '{name}'"
            )

        data = response.json()
        return ScryfallCard(
            name=data.get("name", ""),
            oracle_text=data.get("oracle_text", ""),
            type_line=data.get("type_line", ""),
            mana_cost=data.get("mana_cost", ""),
            keywords=data.get("keywords", []),
        )
    except httpx.TimeoutException as e:
        raise ScryfallError(f"Timeout fetching '{name}': {e}") from e
    finally:
        if should_close:
            await client.aclose()


async def get_cards(
    names: list[str],
    client: Optional[httpx.AsyncClient] = None,
) -> list[ScryfallCard]:
    """Fetch multiple cards with rate limiting and deduplication.

    Cards not found are silently omitted. ScryfallError propagates up.
    """
    unique_names = list(dict.fromkeys(names))
    cards = []
    for i, name in enumerate(unique_names):
        if i > 0:
            await asyncio.sleep(RATE_LIMIT_DELAY)
        card = await get_card(name, client=client)
        if card is not None:
            cards.append(card)
    return cards
