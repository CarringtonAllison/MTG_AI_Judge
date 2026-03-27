"""Parse MTG Comprehensive Rules and seed SQLite database."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.rules_db import init_db, seed_from_file

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "rules.db")
RULES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "comprehensive_rules.txt")


def main():
    print(f"Initializing database at {DB_PATH}")
    init_db(DB_PATH)
    print(f"Seeding from {RULES_FILE}")
    count = seed_from_file(DB_PATH, RULES_FILE)
    print(f"Seeded {count} rules.")


if __name__ == "__main__":
    main()
