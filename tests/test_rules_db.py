import pytest
import os
import sqlite3
from services.rules_db import init_db, seed_from_file, search_by_keywords, get_by_rule_number


@pytest.fixture
def db_path(tmp_path):
    """Provides a temporary database path."""
    return str(tmp_path / "test_rules.db")


@pytest.fixture
def sample_rules_file(tmp_path):
    """Creates a minimal comprehensive rules text file."""
    content = """Magic: The Gathering Comprehensive Rules

These rules are effective as of February 7, 2025.

Introduction

This document is the ultimate authority for Magic: The Gathering competitive game play.

1. Game Concepts

100. General

100.1. These Magic rules apply to any Magic game with two or more players, including two-player games and multiplayer games.

100.2. To play, each player needs their own deck of traditional Magic cards, small items to represent any tokens and counters, and some way to clearly track life totals.

100.2a In constructed play (a way of playing in which each player creates their own deck ahead of time), each deck has a minimum deck size of 60 cards.

100.2b In limited play (a way of playing in which each player gets a quantity of unopened Magic product such as booster packs and creates their own deck using only that product and basic land cards), each deck has a minimum deck size of 40 cards.

7. Additional Rules

702. Keyword Abilities

702.1. Most abilities describe exactly what they do in the rules text of the card they're on.

702.2. Deathtouch

702.2a Deathtouch is a static ability.

702.2b A creature with toughness greater than 0 that's been dealt damage by a source with deathtouch since the last time state-based actions were checked is destroyed as a state-based action.

702.15. Trample

702.15a Trample is a static ability that modifies the rules for assigning an attacking creature's combat damage.

702.15b The controller of an attacking creature with trample first assigns damage to the creature(s) blocking it.

Glossary

Deathtouch
A keyword ability that causes damage dealt by an object to be especially effective.

Trample
A keyword ability that modifies how a creature assigns combat damage.
"""
    rules_file = tmp_path / "rules.txt"
    rules_file.write_text(content, encoding="utf-8")
    return str(rules_file)


class TestInitDb:
    def test_creates_database_file(self, db_path):
        init_db(db_path)
        assert os.path.exists(db_path)

    def test_creates_rules_table(self, db_path):
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rules'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_rules_table_has_correct_columns(self, db_path):
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(rules)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "rule_number" in columns
        assert "rule_text" in columns
        assert "keywords" in columns
        conn.close()

    def test_idempotent_init(self, db_path):
        """Calling init_db twice does not raise."""
        init_db(db_path)
        init_db(db_path)


class TestSeedFromFile:
    def test_seeds_rules(self, db_path, sample_rules_file):
        init_db(db_path)
        count = seed_from_file(db_path, sample_rules_file)
        assert count > 0

    def test_seeds_correct_count(self, db_path, sample_rules_file):
        init_db(db_path)
        count = seed_from_file(db_path, sample_rules_file)
        # Sample file has: 100.1, 100.2, 100.2a, 100.2b,
        # 702.1, 702.2, 702.2a, 702.2b, 702.15, 702.15a, 702.15b = 11 rules
        assert count == 11

    def test_seed_is_idempotent(self, db_path, sample_rules_file):
        """Seeding twice does not duplicate rules."""
        init_db(db_path)
        seed_from_file(db_path, sample_rules_file)
        seed_from_file(db_path, sample_rules_file)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM rules")
        total = cursor.fetchone()[0]
        conn.close()
        assert total == 11


class TestSearchByKeywords:
    def test_search_deathtouch(self, db_path, sample_rules_file):
        init_db(db_path)
        seed_from_file(db_path, sample_rules_file)
        results = search_by_keywords(db_path, ["deathtouch"])
        assert len(results) >= 2
        rule_numbers = [r.rule_number for r in results]
        assert "702.2a" in rule_numbers

    def test_search_trample(self, db_path, sample_rules_file):
        init_db(db_path)
        seed_from_file(db_path, sample_rules_file)
        results = search_by_keywords(db_path, ["trample"])
        assert len(results) >= 2

    def test_search_multiple_keywords(self, db_path, sample_rules_file):
        init_db(db_path)
        seed_from_file(db_path, sample_rules_file)
        results = search_by_keywords(db_path, ["deathtouch", "trample"])
        assert len(results) >= 4

    def test_search_no_results(self, db_path, sample_rules_file):
        init_db(db_path)
        seed_from_file(db_path, sample_rules_file)
        results = search_by_keywords(db_path, ["nonexistentkeyword"])
        assert results == []

    def test_search_case_insensitive(self, db_path, sample_rules_file):
        init_db(db_path)
        seed_from_file(db_path, sample_rules_file)
        results = search_by_keywords(db_path, ["DEATHTOUCH"])
        assert len(results) >= 2


class TestGetByRuleNumber:
    def test_get_existing_rule(self, db_path, sample_rules_file):
        init_db(db_path)
        seed_from_file(db_path, sample_rules_file)
        rule = get_by_rule_number(db_path, "100.1")
        assert rule is not None
        assert rule.rule_number == "100.1"
        assert "Magic rules apply" in rule.rule_text

    def test_get_subrule(self, db_path, sample_rules_file):
        init_db(db_path)
        seed_from_file(db_path, sample_rules_file)
        rule = get_by_rule_number(db_path, "702.2a")
        assert rule is not None
        assert "static ability" in rule.rule_text

    def test_get_nonexistent_rule(self, db_path, sample_rules_file):
        init_db(db_path)
        seed_from_file(db_path, sample_rules_file)
        rule = get_by_rule_number(db_path, "999.99")
        assert rule is None
