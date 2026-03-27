import sqlite3
import re
from typing import Optional
from models.schemas import RulesChunk

# Matches rule lines like "100.1. Text" or "702.2a Text" or "702.15b Text"
RULE_PATTERN = re.compile(r"^(\d{3}\.\d+[a-z]?)\.?\s+(.+)", re.MULTILINE)

# MTG keyword abilities for keyword extraction
MTG_KEYWORDS = [
    "deathtouch", "defender", "double strike", "enchant", "equip",
    "first strike", "flash", "flying", "haste", "hexproof",
    "indestructible", "intimidate", "landwalk", "lifelink", "menace",
    "protection", "prowess", "reach", "shroud", "trample",
    "vigilance", "ward", "cascade", "convoke", "delve",
    "escape", "flashback", "kicker", "madness", "mutate",
    "ninjutsu", "persist", "phasing", "undying", "wither",
    "annihilator", "affinity", "banding", "bushido", "changeling",
    "cycling", "dredge", "evoke", "exalted", "exploit",
    "extort", "fear", "flanking", "forecast", "fortify",
    "graft", "horsemanship", "infect", "living weapon", "morph",
    "offering", "outlast", "overload", "populate", "proliferate",
    "provoke", "rampage", "rebound", "renown", "replicate",
    "retrace", "ripple", "scavenge", "shadow", "soulbond",
    "soulshift", "splice", "split second", "storm", "sunburst",
    "suspend", "totem armor", "transfigure", "transmute", "unearth",
    "unleash", "wither",
]

GAME_CONCEPTS = [
    "damage", "combat", "stack", "priority", "state-based",
    "mana", "cost", "target", "counter", "sacrifice",
    "destroy", "exile", "graveyard", "library", "hand",
    "creature", "artifact", "enchantment", "planeswalker",
    "instant", "sorcery", "land", "token", "copy",
    "triggered", "activated", "static", "replacement",
    "commander", "poison", "energy",
]


def init_db(db_path: str) -> None:
    """Create the rules table if it doesn't exist."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rules (
            rule_number TEXT PRIMARY KEY,
            rule_text TEXT NOT NULL,
            keywords TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()


def _extract_keywords(text: str) -> list[str]:
    """Extract MTG keyword abilities and game concepts found in the rule text."""
    text_lower = text.lower()
    found = set()
    for kw in MTG_KEYWORDS + GAME_CONCEPTS:
        if kw in text_lower:
            found.add(kw)
    return sorted(found)


def _parse_rules(filepath: str) -> list[tuple[str, str, str]]:
    """Parse rules file into (rule_number, rule_text, keywords_csv) tuples."""
    with open(filepath, "r", encoding="utf-8-sig") as f:
        content = f.read()

    # Normalize line endings to \n
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Stop at the second Glossary occurrence (the actual glossary section, not TOC)
    # Find the glossary that appears after the rules content
    glossary_matches = [m.start() for m in re.finditer(r"^\s*Glossary\s*$", content, re.MULTILINE)]
    if len(glossary_matches) >= 2:
        content = content[:glossary_matches[-1]]
    elif len(glossary_matches) == 1:
        content = content[:glossary_matches[0]]

    rules = []
    for match in RULE_PATTERN.finditer(content):
        rule_number = match.group(1)
        rule_text = match.group(2).strip()
        keywords = _extract_keywords(rule_text)
        keywords_csv = ",".join(keywords)
        rules.append((rule_number, rule_text, keywords_csv))
    return rules


def seed_from_file(db_path: str, filepath: str) -> int:
    """Parse rules file and insert into database. Returns count of rules inserted."""
    rules = _parse_rules(filepath)
    conn = sqlite3.connect(db_path)
    conn.executemany(
        "INSERT OR REPLACE INTO rules (rule_number, rule_text, keywords) VALUES (?, ?, ?)",
        rules,
    )
    conn.commit()
    conn.close()
    return len(rules)


def search_by_keywords(db_path: str, keywords: list[str], limit: int = 20) -> list[RulesChunk]:
    """Search rules by keyword matching on both keywords column and rule_text."""
    conn = sqlite3.connect(db_path)
    results = {}
    for kw in keywords:
        kw_lower = kw.lower()
        cursor = conn.execute(
            """
            SELECT rule_number, rule_text, keywords FROM rules
            WHERE LOWER(keywords) LIKE ? OR LOWER(rule_text) LIKE ?
            ORDER BY rule_number
            LIMIT ?
            """,
            (f"%{kw_lower}%", f"%{kw_lower}%", limit),
        )
        for row in cursor.fetchall():
            results[row[0]] = row
    conn.close()

    sorted_rules = sorted(results.values(), key=lambda r: r[0])[:limit]
    return [
        RulesChunk(
            rule_number=r[0],
            rule_text=r[1],
            keywords=r[2].split(",") if r[2] else [],
        )
        for r in sorted_rules
    ]


def get_by_rule_number(db_path: str, rule_number: str) -> Optional[RulesChunk]:
    """Fetch a single rule by its exact rule number. Returns None if not found."""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        "SELECT rule_number, rule_text, keywords FROM rules WHERE rule_number = ?",
        (rule_number,),
    )
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    return RulesChunk(
        rule_number=row[0],
        rule_text=row[1],
        keywords=row[2].split(",") if row[2] else [],
    )
