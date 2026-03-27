import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from models.schemas import (
    JudgeRequest, JudgeResponse, ScryfallCard, RulesChunk, PlayerBoardState,
)
from agents.judge_agent import build_prompt, get_ruling, SYSTEM_PROMPT


class TestBuildPrompt:
    def test_includes_question(self):
        context = {"cards": [], "rules": [], "card_names": [], "web_results": []}
        request = JudgeRequest(
            question="Can I counter a spell on the stack?",
            board_state={},
            life_totals={},
            active_player="player1",
            api_key="key",
        )
        prompt = build_prompt(request, context)
        assert "Can I counter a spell on the stack?" in prompt

    def test_includes_card_oracle_text(self):
        card = ScryfallCard(
            name="Counterspell",
            oracle_text="Counter target spell.",
            type_line="Instant",
            mana_cost="{U}{U}",
            keywords=[],
        )
        context = {"cards": [card], "rules": [], "card_names": ["Counterspell"], "web_results": []}
        request = JudgeRequest(
            question="test", board_state={}, life_totals={},
            active_player="player1", api_key="key",
        )
        prompt = build_prompt(request, context)
        assert "Counter target spell." in prompt
        assert "Counterspell" in prompt

    def test_includes_rules(self):
        rule = RulesChunk(
            rule_number="601.2",
            rule_text="To cast a spell is to take it from where it is...",
            keywords=["cast"],
        )
        context = {"cards": [], "rules": [rule], "card_names": [], "web_results": []}
        request = JudgeRequest(
            question="test", board_state={}, life_totals={},
            active_player="player1", api_key="key",
        )
        prompt = build_prompt(request, context)
        assert "601.2" in prompt
        assert "To cast a spell" in prompt

    def test_includes_board_state(self):
        request = JudgeRequest(
            question="test",
            board_state={
                "player1": PlayerBoardState(
                    battlefield=["Forest", "Llanowar Elves"],
                    graveyard=[],
                    exile=[],
                    hand_count=6,
                ),
            },
            life_totals={"player1": 18},
            active_player="player1",
            api_key="key",
        )
        context = {"cards": [], "rules": [], "card_names": [], "web_results": []}
        prompt = build_prompt(request, context)
        assert "Forest" in prompt
        assert "Llanowar Elves" in prompt
        assert "18" in prompt

    def test_includes_active_player(self):
        request = JudgeRequest(
            question="test", board_state={}, life_totals={},
            active_player="player2", api_key="key",
        )
        context = {"cards": [], "rules": [], "card_names": [], "web_results": []}
        prompt = build_prompt(request, context)
        assert "player2" in prompt

    def test_system_prompt_content(self):
        """System prompt establishes judge persona and output format."""
        assert "judge" in SYSTEM_PROMPT.lower() or "Judge" in SYSTEM_PROMPT
        assert "JSON" in SYSTEM_PROMPT or "json" in SYSTEM_PROMPT

    def test_includes_web_results_when_present(self):
        web_results = [
            {"source": "reddit", "title": "Bolt vs Walker", "snippet": "Yes you can.", "url": "https://reddit.com/r/mtgrules/abc"}
        ]
        context = {"cards": [], "rules": [], "card_names": [], "web_results": web_results}
        request = JudgeRequest(
            question="test", board_state={}, life_totals={},
            active_player="player1", api_key="key",
        )
        prompt = build_prompt(request, context)
        assert "Bolt vs Walker" in prompt
        assert "reddit.com" in prompt

    def test_web_results_section_absent_when_empty(self):
        context = {"cards": [], "rules": [], "card_names": [], "web_results": []}
        request = JudgeRequest(
            question="test", board_state={}, life_totals={},
            active_player="player1", api_key="key",
        )
        prompt = build_prompt(request, context)
        assert "WEB SOURCES" not in prompt


class TestGetRuling:
    def _make_mock_response(self, text):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=text)]
        return mock_response

    @pytest.mark.asyncio
    async def test_calls_claude_with_correct_model(self):
        response_json = json.dumps({
            "ruling": "Yes, you can counter it.",
            "explanation": "Counterspell targets any spell on the stack.",
            "rules_cited": ["601.2"],
            "cards_referenced": ["Counterspell"],
        })
        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=self._make_mock_response(response_json))

        with patch("agents.judge_agent.anthropic.AsyncAnthropic", return_value=mock_client):
            request = JudgeRequest(
                question="test", board_state={}, life_totals={},
                active_player="player1", api_key="test-api-key",
            )
            context = {"cards": [], "rules": [], "card_names": [], "web_results": []}
            await get_ruling(request, context)

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-6"
        assert call_kwargs["max_tokens"] == 1024

    @pytest.mark.asyncio
    async def test_passes_api_key_to_client(self):
        response_json = json.dumps({
            "ruling": "r", "explanation": "e",
            "rules_cited": [], "cards_referenced": [],
        })
        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=self._make_mock_response(response_json))

        with patch("agents.judge_agent.anthropic.AsyncAnthropic", return_value=mock_client) as mock_cls:
            request = JudgeRequest(
                question="t", board_state={}, life_totals={},
                active_player="p1", api_key="sk-ant-my-key",
            )
            context = {"cards": [], "rules": [], "card_names": [], "web_results": []}
            await get_ruling(request, context)

        mock_cls.assert_called_once_with(api_key="sk-ant-my-key")

    @pytest.mark.asyncio
    async def test_returns_judge_response(self):
        response_json = json.dumps({
            "ruling": "No, you cannot.",
            "explanation": "Because...",
            "rules_cited": ["100.1"],
            "cards_referenced": ["Forest"],
        })
        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=self._make_mock_response(response_json))

        with patch("agents.judge_agent.anthropic.AsyncAnthropic", return_value=mock_client):
            request = JudgeRequest(
                question="t", board_state={}, life_totals={},
                active_player="p1", api_key="key",
            )
            context = {"cards": [], "rules": [], "card_names": [], "web_results": []}
            result = await get_ruling(request, context)

        assert isinstance(result, JudgeResponse)
        assert result.ruling == "No, you cannot."
        assert "100.1" in result.rules_cited

    @pytest.mark.asyncio
    async def test_handles_malformed_json_from_claude(self):
        """Falls back gracefully when Claude returns non-JSON."""
        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=self._make_mock_response("Sorry, I can't help with that.")
        )

        with patch("agents.judge_agent.anthropic.AsyncAnthropic", return_value=mock_client):
            request = JudgeRequest(
                question="t", board_state={}, life_totals={},
                active_player="p1", api_key="key",
            )
            context = {"cards": [], "rules": [], "card_names": [], "web_results": []}
            result = await get_ruling(request, context)

        assert isinstance(result, JudgeResponse)
        assert "Sorry" in result.ruling

    @pytest.mark.asyncio
    async def test_handles_api_error(self):
        """Returns error response when Claude API fails."""
        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(
            side_effect=Exception("API rate limit exceeded")
        )

        with patch("agents.judge_agent.anthropic.AsyncAnthropic", return_value=mock_client):
            request = JudgeRequest(
                question="t", board_state={}, life_totals={},
                active_player="p1", api_key="key",
            )
            context = {"cards": [], "rules": [], "card_names": [], "web_results": []}
            result = await get_ruling(request, context)

        assert isinstance(result, JudgeResponse)
        assert "error" in result.ruling.lower() or "Error" in result.ruling

    @pytest.mark.asyncio
    async def test_conversation_history_included_in_messages(self):
        """When session history is provided, prior Q&A pairs are included."""
        response_json = json.dumps({
            "ruling": "r", "explanation": "e",
            "rules_cited": [], "cards_referenced": [],
        })
        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=self._make_mock_response(response_json))

        session_history = [
            {"role": "user", "content": "Can I bolt a walker?"},
            {"role": "assistant", "content": "Yes you can."},
        ]

        with patch("agents.judge_agent.anthropic.AsyncAnthropic", return_value=mock_client):
            request = JudgeRequest(
                question="What about hexproof?", board_state={}, life_totals={},
                active_player="p1", api_key="key",
            )
            context = {"cards": [], "rules": [], "card_names": [], "web_results": []}
            await get_ruling(request, context, session_history=session_history)

        call_kwargs = mock_client.messages.create.call_args[1]
        messages = call_kwargs["messages"]
        # Should have prior history + current question
        assert len(messages) >= 3
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Can I bolt a walker?"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Yes you can."
