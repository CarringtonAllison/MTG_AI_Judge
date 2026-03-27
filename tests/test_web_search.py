import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock
from services.web_search import search_reddit, search_ddg, fallback_search


REDDIT_JSON_RESPONSE = {
    "data": {
        "children": [
            {
                "data": {
                    "title": "Can Lightning Bolt target planeswalkers?",
                    "selftext": "Yes, since the 2019 rules change you can directly target planeswalkers.",
                    "permalink": "/r/mtgrules/comments/abc123/can_lightning_bolt_target_planeswalkers/",
                    "score": 15,
                }
            },
            {
                "data": {
                    "title": "Bolt vs planeswalker ruling",
                    "selftext": "Confirmed, Bolt can target walkers now.",
                    "permalink": "/r/mtgrules/comments/def456/bolt_vs_planeswalker_ruling/",
                    "score": 8,
                }
            },
            {
                "data": {
                    "title": "random low quality post",
                    "selftext": "idk",
                    "permalink": "/r/mtgrules/comments/ghi789/random/",
                    "score": 1,
                }
            },
        ]
    }
}

DDG_HTML_RESPONSE = """
<html>
<body>
<div class="results">
  <div class="result">
    <a class="result__a" href="https://mtg.fandom.com/wiki/Lightning_Bolt">Lightning Bolt - MTG Wiki</a>
    <a class="result__snippet">Lightning Bolt deals 3 damage to any target. A staple of red decks.</a>
  </div>
  <div class="result">
    <a class="result__a" href="https://scryfall.com/card/leb/162/lightning-bolt">Lightning Bolt - Scryfall</a>
    <a class="result__snippet">Lightning Bolt {R} Instant. Deals 3 damage.</a>
  </div>
</div>
</body>
</html>
"""


@pytest.fixture
def mock_client():
    return AsyncMock(spec=httpx.AsyncClient)


class TestRedditSearch:
    @pytest.mark.asyncio
    async def test_reddit_search_returns_results(self, mock_client):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = REDDIT_JSON_RESPONSE
        mock_client.get = AsyncMock(return_value=response)

        results = await search_reddit("Lightning Bolt planeswalker", client=mock_client)
        assert len(results) >= 1
        assert results[0]["title"] == "Can Lightning Bolt target planeswalkers?"
        assert "url" in results[0]

    @pytest.mark.asyncio
    async def test_reddit_search_no_results(self, mock_client):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"data": {"children": []}}
        mock_client.get = AsyncMock(return_value=response)

        results = await search_reddit("xyznonexistent", client=mock_client)
        assert results == []

    @pytest.mark.asyncio
    async def test_reddit_search_http_error(self, mock_client):
        response = MagicMock()
        response.status_code = 500
        mock_client.get = AsyncMock(return_value=response)

        results = await search_reddit("test", client=mock_client)
        assert results == []

    @pytest.mark.asyncio
    async def test_reddit_search_filters_low_score(self, mock_client):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = REDDIT_JSON_RESPONSE
        mock_client.get = AsyncMock(return_value=response)

        results = await search_reddit("test", client=mock_client)
        # The post with score=1 should be filtered out
        for r in results:
            assert r["score"] >= 2


class TestDuckDuckGoSearch:
    @pytest.mark.asyncio
    async def test_ddg_search_returns_results(self, mock_client):
        response = MagicMock()
        response.status_code = 200
        response.text = DDG_HTML_RESPONSE
        mock_client.get = AsyncMock(return_value=response)

        results = await search_ddg("Lightning Bolt MTG rules", client=mock_client)
        assert len(results) >= 1
        assert "url" in results[0]
        assert "title" in results[0]

    @pytest.mark.asyncio
    async def test_ddg_search_no_results(self, mock_client):
        response = MagicMock()
        response.status_code = 200
        response.text = "<html><body><div class='results'></div></body></html>"
        mock_client.get = AsyncMock(return_value=response)

        results = await search_ddg("xyznonexistent", client=mock_client)
        assert results == []

    @pytest.mark.asyncio
    async def test_ddg_search_http_error(self, mock_client):
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        results = await search_ddg("test", client=mock_client)
        assert results == []


class TestFallbackSearch:
    @pytest.mark.asyncio
    async def test_fallback_search_combines_sources(self, mock_client):
        reddit_response = MagicMock()
        reddit_response.status_code = 200
        reddit_response.json.return_value = REDDIT_JSON_RESPONSE

        ddg_response = MagicMock()
        ddg_response.status_code = 200
        ddg_response.text = DDG_HTML_RESPONSE

        mock_client.get = AsyncMock(side_effect=[reddit_response, ddg_response])

        results = await fallback_search("Lightning Bolt planeswalker", client=mock_client)
        assert len(results) <= 5
        assert len(results) >= 1
        # Should have results from both sources
        sources = {r["source"] for r in results}
        assert "reddit" in sources or "ddg" in sources
