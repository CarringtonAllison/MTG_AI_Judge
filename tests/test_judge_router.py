import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from main import app
from models.schemas import JudgeResponse


@pytest.fixture
def valid_payload():
    return {
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
        "api_key": "sk-ant-test-key",
        "session_id": "player1_white",
    }


@pytest.fixture
def mock_ruling():
    return JudgeResponse(
        ruling="Yes, Lightning Bolt can target a planeswalker directly.",
        explanation="Since the 2019 rules update...",
        rules_cited=["306.7"],
        cards_referenced=["Lightning Bolt", "Jace, the Mind Sculptor"],
    )


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_200(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestJudgeEndpoint:
    @pytest.mark.asyncio
    async def test_valid_request_returns_200(self, valid_payload, mock_ruling):
        with patch("routers.judge.build_context", new_callable=AsyncMock) as mock_ctx, \
             patch("routers.judge.get_ruling", new_callable=AsyncMock) as mock_judge, \
             patch("routers.judge.cleanup_expired"), \
             patch("routers.judge.get_history", return_value=[]), \
             patch("routers.judge.add_exchange"):
            mock_ctx.return_value = {"cards": [], "rules": [], "card_names": [], "web_results": []}
            mock_judge.return_value = mock_ruling

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post("/judge", json=valid_payload)

            assert response.status_code == 200
            data = response.json()
            assert "ruling" in data
            assert "explanation" in data
            assert "rules_cited" in data

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_422(self):
        payload = {
            "question": "test",
            "board_state": {},
            "life_totals": {},
            "active_player": "player1",
        }
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/judge", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_question_returns_422(self):
        payload = {
            "board_state": {},
            "life_totals": {},
            "active_player": "player1",
            "api_key": "key",
        }
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/judge", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_question_returns_422(self):
        payload = {
            "question": "",
            "board_state": {},
            "life_totals": {},
            "active_player": "player1",
            "api_key": "key",
        }
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/judge", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_board_state_type_returns_422(self):
        payload = {
            "question": "test",
            "board_state": {"player1": "not a dict"},
            "life_totals": {},
            "active_player": "player1",
            "api_key": "key",
        }
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/judge", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_response_structure_matches_schema(self, valid_payload, mock_ruling):
        with patch("routers.judge.build_context", new_callable=AsyncMock) as mock_ctx, \
             patch("routers.judge.get_ruling", new_callable=AsyncMock) as mock_judge, \
             patch("routers.judge.cleanup_expired"), \
             patch("routers.judge.get_history", return_value=[]), \
             patch("routers.judge.add_exchange"):
            mock_ctx.return_value = {"cards": [], "rules": [], "card_names": [], "web_results": []}
            mock_judge.return_value = mock_ruling

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post("/judge", json=valid_payload)

            data = response.json()
            assert isinstance(data["ruling"], str)
            assert isinstance(data["explanation"], str)
            assert isinstance(data["rules_cited"], list)
            assert isinstance(data["cards_referenced"], list)

    @pytest.mark.asyncio
    async def test_session_id_echoed_in_response(self, valid_payload, mock_ruling):
        with patch("routers.judge.build_context", new_callable=AsyncMock) as mock_ctx, \
             patch("routers.judge.get_ruling", new_callable=AsyncMock) as mock_judge, \
             patch("routers.judge.cleanup_expired"), \
             patch("routers.judge.get_history", return_value=[]), \
             patch("routers.judge.add_exchange"):
            mock_ctx.return_value = {"cards": [], "rules": [], "card_names": [], "web_results": []}
            mock_judge.return_value = mock_ruling

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post("/judge", json=valid_payload)

            data = response.json()
            assert data["session_id"] == "player1_white"

    @pytest.mark.asyncio
    async def test_session_history_passed_to_judge_agent(self, valid_payload, mock_ruling):
        history = [{"role": "user", "content": "prior Q"}, {"role": "assistant", "content": "prior A"}]

        with patch("routers.judge.build_context", new_callable=AsyncMock) as mock_ctx, \
             patch("routers.judge.get_ruling", new_callable=AsyncMock) as mock_judge, \
             patch("routers.judge.cleanup_expired"), \
             patch("routers.judge.get_history", return_value=history), \
             patch("routers.judge.add_exchange"):
            mock_ctx.return_value = {"cards": [], "rules": [], "card_names": [], "web_results": []}
            mock_judge.return_value = mock_ruling

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                await ac.post("/judge", json=valid_payload)

            # Verify get_ruling was called with session_history
            call_kwargs = mock_judge.call_args[1]
            assert call_kwargs["session_history"] == history

    @pytest.mark.asyncio
    async def test_exchange_stored_after_ruling(self, valid_payload, mock_ruling):
        with patch("routers.judge.build_context", new_callable=AsyncMock) as mock_ctx, \
             patch("routers.judge.get_ruling", new_callable=AsyncMock) as mock_judge, \
             patch("routers.judge.cleanup_expired"), \
             patch("routers.judge.get_history", return_value=[]), \
             patch("routers.judge.add_exchange") as mock_add:
            mock_ctx.return_value = {"cards": [], "rules": [], "card_names": [], "web_results": []}
            mock_judge.return_value = mock_ruling

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                await ac.post("/judge", json=valid_payload)

            mock_add.assert_called_once_with(
                "player1_white",
                "Can [[Lightning Bolt]] target a planeswalker?",
                mock_ruling.ruling,
            )
