import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock
from services.scryfall import get_card, get_cards, ScryfallError


BOLT_RESPONSE = {
    "name": "Lightning Bolt",
    "oracle_text": "Lightning Bolt deals 3 damage to any target.",
    "type_line": "Instant",
    "mana_cost": "{R}",
    "keywords": [],
}

JACE_RESPONSE = {
    "name": "Jace, the Mind Sculptor",
    "oracle_text": "[+2]: Look at the top card of target player's library...",
    "type_line": "Legendary Planeswalker — Jace",
    "mana_cost": "{2}{U}{U}",
    "keywords": [],
}


@pytest.fixture
def mock_client():
    """Provides a mocked httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


class TestGetCard:
    @pytest.mark.asyncio
    async def test_fetches_card_by_fuzzy_name(self, mock_client):
        """Successfully fetches a card and returns ScryfallCard."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = BOLT_RESPONSE
        mock_client.get = AsyncMock(return_value=response)

        card = await get_card("Lightning Bolt", client=mock_client)
        assert card.name == "Lightning Bolt"
        assert "3 damage" in card.oracle_text
        assert card.type_line == "Instant"
        mock_client.get.assert_called_once_with(
            "https://api.scryfall.com/cards/named",
            params={"fuzzy": "Lightning Bolt"},
        )

    @pytest.mark.asyncio
    async def test_card_not_found_returns_none(self, mock_client):
        """Returns None when Scryfall returns 404."""
        response = MagicMock()
        response.status_code = 404
        response.json.return_value = {"status": 404, "details": "Not found"}
        mock_client.get = AsyncMock(return_value=response)

        card = await get_card("Nonexistent Card XYZ", client=mock_client)
        assert card is None

    @pytest.mark.asyncio
    async def test_http_error_raises_scryfall_error(self, mock_client):
        """Raises ScryfallError on 500 server error."""
        response = MagicMock()
        response.status_code = 500
        response.text = "Internal Server Error"
        mock_client.get = AsyncMock(return_value=response)

        with pytest.raises(ScryfallError):
            await get_card("Lightning Bolt", client=mock_client)

    @pytest.mark.asyncio
    async def test_timeout_raises_scryfall_error(self, mock_client):
        """Raises ScryfallError on request timeout."""
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with pytest.raises(ScryfallError):
            await get_card("Lightning Bolt", client=mock_client)

    @pytest.mark.asyncio
    async def test_parses_keywords(self, mock_client):
        """Correctly parses card keywords list."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "name": "Questing Beast",
            "oracle_text": "Vigilance, deathtouch, haste...",
            "type_line": "Legendary Creature — Beast",
            "mana_cost": "{2}{G}{G}",
            "keywords": ["Vigilance", "Deathtouch", "Haste"],
        }
        mock_client.get = AsyncMock(return_value=response)

        card = await get_card("Questing Beast", client=mock_client)
        assert "Haste" in card.keywords

    @pytest.mark.asyncio
    async def test_missing_oracle_text_defaults_empty(self, mock_client):
        """Cards without oracle_text (e.g., basic lands) get empty string."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "name": "Forest",
            "type_line": "Basic Land — Forest",
            "mana_cost": "",
            "keywords": [],
        }
        mock_client.get = AsyncMock(return_value=response)

        card = await get_card("Forest", client=mock_client)
        assert card.oracle_text == ""


class TestGetCards:
    @pytest.mark.asyncio
    async def test_fetches_multiple_cards(self, mock_client):
        """Fetches multiple cards, returns list in order."""
        responses = [
            MagicMock(status_code=200, json=MagicMock(return_value=BOLT_RESPONSE)),
            MagicMock(status_code=200, json=MagicMock(return_value=JACE_RESPONSE)),
        ]
        mock_client.get = AsyncMock(side_effect=responses)

        cards = await get_cards(["Lightning Bolt", "Jace, the Mind Sculptor"], client=mock_client)
        assert len(cards) == 2
        assert cards[0].name == "Lightning Bolt"
        assert cards[1].name == "Jace, the Mind Sculptor"

    @pytest.mark.asyncio
    async def test_skips_not_found_cards(self, mock_client):
        """Cards not found on Scryfall are omitted from results."""
        responses = [
            MagicMock(status_code=200, json=MagicMock(return_value=BOLT_RESPONSE)),
            MagicMock(status_code=404, json=MagicMock(return_value={"status": 404})),
        ]
        mock_client.get = AsyncMock(side_effect=responses)

        cards = await get_cards(["Lightning Bolt", "Fake Card"], client=mock_client)
        assert len(cards) == 1

    @pytest.mark.asyncio
    async def test_empty_list_returns_empty(self, mock_client):
        """Empty input list returns empty output."""
        cards = await get_cards([], client=mock_client)
        assert cards == []

    @pytest.mark.asyncio
    async def test_deduplicates_card_names(self, mock_client):
        """Duplicate card names only fetch once."""
        response = MagicMock(status_code=200, json=MagicMock(return_value=BOLT_RESPONSE))
        mock_client.get = AsyncMock(return_value=response)

        cards = await get_cards(["Lightning Bolt", "Lightning Bolt"], client=mock_client)
        assert len(cards) == 1
        assert mock_client.get.call_count == 1
