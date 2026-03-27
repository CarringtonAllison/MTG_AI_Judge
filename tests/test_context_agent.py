import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from models.schemas import ScryfallCard, RulesChunk, JudgeRequest, PlayerBoardState
from agents.context_agent import extract_card_names, build_context


class TestExtractCardNames:
    def test_extracts_double_bracket_syntax(self):
        """Extracts card names in [[Card Name]] notation."""
        question = "Can [[Lightning Bolt]] target [[Jace, the Mind Sculptor]]?"
        names = extract_card_names(question, {})
        assert "Lightning Bolt" in names
        assert "Jace, the Mind Sculptor" in names

    def test_extracts_from_board_state(self):
        """Extracts card names from battlefield, graveyard, exile."""
        board = {
            "player1": PlayerBoardState(
                battlefield=["Tarmogoyf", "Forest"],
                graveyard=["Fatal Push"],
                exile=["Leyline of the Void"],
                hand_count=5,
            ),
        }
        names = extract_card_names("What happens?", board)
        assert "Tarmogoyf" in names
        assert "Fatal Push" in names
        assert "Leyline of the Void" in names

    def test_deduplicates_names(self):
        """Same card in question and board only appears once."""
        board = {
            "player1": PlayerBoardState(
                battlefield=["Lightning Bolt"],
                graveyard=[],
                exile=[],
                hand_count=3,
            ),
        }
        names = extract_card_names("Can [[Lightning Bolt]] do this?", board)
        assert names.count("Lightning Bolt") == 1

    def test_no_cards_found(self):
        """Returns empty list when no cards are identifiable."""
        names = extract_card_names("How does the stack work?", {})
        assert names == []

    def test_extracts_from_question_without_brackets(self):
        """Does NOT attempt NLP extraction from bare text (only brackets + board)."""
        names = extract_card_names("Can Lightning Bolt target a player?", {})
        assert names == []

    def test_handles_basic_lands(self):
        """Basic lands from board state are included and deduplicated."""
        board = {
            "player1": PlayerBoardState(
                battlefield=["Island", "Island", "Swamp"],
                graveyard=[],
                exile=[],
                hand_count=4,
            ),
        }
        names = extract_card_names("", board)
        assert "Island" in names
        assert "Swamp" in names
        assert len(names) == 2


class TestBuildContext:
    @pytest.mark.asyncio
    async def test_builds_full_context(self):
        """Assembles cards + rules into context dict."""
        bolt = ScryfallCard(
            name="Lightning Bolt",
            oracle_text="Lightning Bolt deals 3 damage to any target.",
            type_line="Instant",
            mana_cost="{R}",
            keywords=[],
        )
        rule = RulesChunk(
            rule_number="702.2a",
            rule_text="Deathtouch is a static ability.",
            keywords=["deathtouch"],
        )

        with patch("agents.context_agent.get_cards", new_callable=AsyncMock) as mock_scryfall, \
             patch("agents.context_agent.search_by_keywords") as mock_rules, \
             patch("agents.context_agent.fallback_search", new_callable=AsyncMock) as mock_fallback:
            mock_scryfall.return_value = [bolt]
            mock_rules.return_value = [rule, rule]  # >= 2 results, no fallback needed
            mock_fallback.return_value = []

            request = JudgeRequest(
                question="Does [[Lightning Bolt]] kill a creature with deathtouch?",
                board_state={},
                life_totals={"player1": 20},
                active_player="player1",
                api_key="test-key",
            )
            context = await build_context(request)

        assert "cards" in context
        assert len(context["cards"]) == 1
        assert context["cards"][0].name == "Lightning Bolt"
        assert "rules" in context
        assert len(context["rules"]) >= 1

    @pytest.mark.asyncio
    async def test_context_with_no_cards_found(self):
        """Context still works when Scryfall returns nothing."""
        with patch("agents.context_agent.get_cards", new_callable=AsyncMock) as mock_scryfall, \
             patch("agents.context_agent.search_by_keywords") as mock_rules, \
             patch("agents.context_agent.fallback_search", new_callable=AsyncMock) as mock_fallback:
            mock_scryfall.return_value = []
            mock_rules.return_value = []
            mock_fallback.return_value = []

            request = JudgeRequest(
                question="How does the stack work?",
                board_state={},
                life_totals={},
                active_player="player1",
                api_key="test-key",
            )
            context = await build_context(request)

        assert context["cards"] == []

    @pytest.mark.asyncio
    async def test_keywords_derived_from_cards_and_question(self):
        """Rules search uses keywords from card oracle text and question."""
        card = ScryfallCard(
            name="Questing Beast",
            oracle_text="Vigilance, deathtouch, haste...",
            type_line="Legendary Creature — Beast",
            mana_cost="{2}{G}{G}",
            keywords=["Vigilance", "Deathtouch", "Haste"],
        )

        with patch("agents.context_agent.get_cards", new_callable=AsyncMock) as mock_scryfall, \
             patch("agents.context_agent.search_by_keywords") as mock_rules, \
             patch("agents.context_agent.fallback_search", new_callable=AsyncMock) as mock_fallback:
            mock_scryfall.return_value = [card]
            mock_rules.return_value = [MagicMock() for _ in range(3)]
            mock_fallback.return_value = []

            request = JudgeRequest(
                question="Does [[Questing Beast]] have trample?",
                board_state={},
                life_totals={},
                active_player="player1",
                api_key="test-key",
            )
            context = await build_context(request)

        # Verify search_by_keywords was called with keywords from the card
        call_args = mock_rules.call_args
        keywords_used = call_args[0][1]  # second positional arg is keywords list
        keywords_lower = [k.lower() for k in keywords_used]
        assert any(kw in keywords_lower for kw in ["deathtouch", "vigilance", "haste", "trample"])

    @pytest.mark.asyncio
    async def test_web_fallback_triggered_when_rules_empty(self):
        """When rules DB returns few results, fallback_search is called."""
        with patch("agents.context_agent.get_cards", new_callable=AsyncMock) as mock_scryfall, \
             patch("agents.context_agent.search_by_keywords") as mock_rules, \
             patch("agents.context_agent.fallback_search", new_callable=AsyncMock) as mock_fallback:
            mock_scryfall.return_value = []
            mock_rules.return_value = []  # No rules found
            mock_fallback.return_value = [{"source": "reddit", "title": "test", "snippet": "answer", "url": "http://example.com"}]

            request = JudgeRequest(
                question="Some obscure question",
                board_state={},
                life_totals={},
                active_player="player1",
                api_key="test-key",
            )
            context = await build_context(request)

        mock_fallback.assert_called_once()
        assert len(context["web_results"]) == 1

    @pytest.mark.asyncio
    async def test_web_fallback_not_triggered_when_rules_found(self):
        """When rules DB returns sufficient results, fallback_search is NOT called."""
        rule = RulesChunk(rule_number="100.1", rule_text="test", keywords=[])

        with patch("agents.context_agent.get_cards", new_callable=AsyncMock) as mock_scryfall, \
             patch("agents.context_agent.search_by_keywords") as mock_rules, \
             patch("agents.context_agent.fallback_search", new_callable=AsyncMock) as mock_fallback:
            mock_scryfall.return_value = []
            mock_rules.return_value = [rule, rule]  # 2 results = sufficient
            mock_fallback.return_value = []

            request = JudgeRequest(
                question="How does trample damage work?",
                board_state={},
                life_totals={},
                active_player="player1",
                api_key="test-key",
            )
            context = await build_context(request)

        mock_fallback.assert_not_called()
        assert context["web_results"] == []
