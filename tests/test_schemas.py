import pytest
from pydantic import ValidationError
from models.schemas import (
    JudgeRequest,
    JudgeResponse,
    ScryfallCard,
    RulesChunk,
    PlayerBoardState,
)


class TestJudgeRequest:
    def test_valid_minimal_request(self):
        """Accepts a valid request with all required fields."""
        data = {
            "question": "Can I Lightning Bolt a planeswalker?",
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
        }
        req = JudgeRequest(**data)
        assert req.question == "Can I Lightning Bolt a planeswalker?"
        assert req.active_player == "player1"
        assert req.api_key == "sk-ant-test-key"
        assert req.board_state["player1"].hand_count == 6
        assert req.session_id == ""  # default

    def test_missing_question_raises(self):
        """Rejects request missing the question field."""
        data = {
            "board_state": {},
            "life_totals": {},
            "active_player": "player1",
            "api_key": "sk-ant-test-key",
        }
        with pytest.raises(ValidationError) as exc_info:
            JudgeRequest(**data)
        assert "question" in str(exc_info.value)

    def test_missing_api_key_raises(self):
        """Rejects request missing the api_key field."""
        data = {
            "question": "test",
            "board_state": {},
            "life_totals": {},
            "active_player": "player1",
        }
        with pytest.raises(ValidationError):
            JudgeRequest(**data)

    def test_empty_question_raises(self):
        """Rejects empty string question."""
        data = {
            "question": "",
            "board_state": {},
            "life_totals": {},
            "active_player": "player1",
            "api_key": "sk-ant-test-key",
        }
        with pytest.raises(ValidationError):
            JudgeRequest(**data)

    def test_board_state_with_four_players(self):
        """Accepts up to 4 players in board_state."""
        player_template = {
            "battlefield": [],
            "graveyard": [],
            "exile": [],
            "hand_count": 7,
        }
        data = {
            "question": "test",
            "board_state": {f"player{i}": player_template for i in range(1, 5)},
            "life_totals": {f"player{i}": 40 for i in range(1, 5)},
            "active_player": "player1",
            "api_key": "key",
        }
        req = JudgeRequest(**data)
        assert len(req.board_state) == 4

    def test_invalid_life_total_type_raises(self):
        """Rejects non-integer life totals."""
        data = {
            "question": "test",
            "board_state": {},
            "life_totals": {"player1": "twenty"},
            "active_player": "player1",
            "api_key": "key",
        }
        with pytest.raises(ValidationError):
            JudgeRequest(**data)


class TestJudgeResponse:
    def test_valid_response(self):
        resp = JudgeResponse(
            ruling="Yes, you can target a planeswalker.",
            explanation="Since 2019 rules update, damage redirection removed.",
            rules_cited=["306.7", "118.1"],
            cards_referenced=["Lightning Bolt", "Jace, the Mind Sculptor"],
        )
        assert len(resp.rules_cited) == 2
        assert resp.ruling.startswith("Yes")
        assert resp.session_id == ""
        assert resp.web_sources == []

    def test_empty_lists_allowed(self):
        resp = JudgeResponse(
            ruling="Unclear.",
            explanation="Not enough info.",
            rules_cited=[],
            cards_referenced=[],
        )
        assert resp.rules_cited == []


class TestScryfallCard:
    def test_valid_instant(self):
        """Validates an instant card (Lightning Bolt)."""
        card = ScryfallCard(
            name="Lightning Bolt",
            oracle_text="Lightning Bolt deals 3 damage to any target.",
            type_line="Instant",
            mana_cost="{R}",
            keywords=[],
        )
        assert card.name == "Lightning Bolt"
        assert card.type_line == "Instant"
        assert "3 damage" in card.oracle_text

    def test_valid_creature(self):
        """Validates a creature card (Tarmogoyf)."""
        card = ScryfallCard(
            name="Tarmogoyf",
            oracle_text="Tarmogoyf's power is equal to the number of card types among cards in all graveyards and its toughness is equal to that number plus 1.",
            type_line="Creature — Lhurgoyf",
            mana_cost="{1}{G}",
            keywords=[],
        )
        assert card.name == "Tarmogoyf"
        assert "Creature" in card.type_line
        assert "Lhurgoyf" in card.type_line

    def test_valid_planeswalker(self):
        """Validates a planeswalker card (Jace, the Mind Sculptor)."""
        card = ScryfallCard(
            name="Jace, the Mind Sculptor",
            oracle_text="+2: Look at the top card of target player's library. You may put that card on the bottom of that player's library.\n0: Draw three cards, then put two cards from your hand on top of your library in any order.\n−1: Return target creature to its owner's hand.\n−12: Exile all cards from target player's library, then that player shuffles their hand into their library.",
            type_line="Legendary Planeswalker — Jace",
            mana_cost="{2}{U}{U}",
            keywords=[],
        )
        assert card.name == "Jace, the Mind Sculptor"
        assert "Planeswalker" in card.type_line
        assert "Legendary" in card.type_line

    def test_valid_enchantment(self):
        """Validates an enchantment card (Rhystic Study)."""
        card = ScryfallCard(
            name="Rhystic Study",
            oracle_text="Whenever an opponent casts a spell, you may draw a card unless that player pays {1}.",
            type_line="Enchantment",
            mana_cost="{2}{U}",
            keywords=[],
        )
        assert card.name == "Rhystic Study"
        assert card.type_line == "Enchantment"
        assert "draw a card" in card.oracle_text

    def test_valid_secret_lair_alternate_art(self):
        """Validates a Secret Lair / alternate art card parses with the same fields."""
        card = ScryfallCard(
            name="Lightning Bolt",
            oracle_text="Lightning Bolt deals 3 damage to any target.",
            type_line="Instant",
            mana_cost="{R}",
            keywords=[],
        )
        # Secret Lair cards have the same oracle text/fields — the art is different
        # but the data model is identical. Verify all fields are populated.
        assert card.name == "Lightning Bolt"
        assert card.oracle_text != ""
        assert card.type_line != ""
        assert card.mana_cost != ""

    def test_card_with_keywords(self):
        """Validates a card with multiple keyword abilities."""
        card = ScryfallCard(
            name="Questing Beast",
            oracle_text="Vigilance, deathtouch, haste\nQuesting Beast can't be blocked by creatures with power 2 or less.",
            type_line="Legendary Creature — Beast",
            mana_cost="{2}{G}{G}",
            keywords=["Vigilance", "Deathtouch", "Haste"],
        )
        assert "Haste" in card.keywords
        assert "Deathtouch" in card.keywords
        assert "Vigilance" in card.keywords
        assert len(card.keywords) == 3


class TestRulesChunk:
    def test_valid_rule(self):
        rule = RulesChunk(
            rule_number="702.2",
            rule_text="Deathtouch is a static ability.",
            keywords=["deathtouch"],
        )
        assert rule.rule_number == "702.2"

    def test_empty_keywords(self):
        rule = RulesChunk(
            rule_number="100.1",
            rule_text="These Magic rules apply to any Magic game with two or more players.",
            keywords=[],
        )
        assert rule.keywords == []
