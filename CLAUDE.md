# CLAUDE.md

## Commit Policy
Commit after every discrete, working unit of work. Do not batch multiple features into one commit.

Each of the following always gets its own commit:
- New file or module created
- Tests written
- Features implemented
- Config or dependency change
- Bug fix

If more than ~3 files changed for unrelated reasons, split into multiple commits.

Commit message format: `scope: short description`
Examples: `backend: add health endpoint`, `frontend: update status indicator`, `tests: add schema validation tests`

Do **not** include a `Co-Authored-By` trailer in commit messages.

## Project
- Python 3.12, FastAPI, SQLite, Anthropic Claude API, Scryfall REST API
- TDD: always write tests before implementation
- Run tests with: `python -m pytest tests/ -v`
- Python path: `/c/Users/Rain_/AppData/Local/Programs/Python/Python312/python.exe`
