# MTG AI Judge

AI-powered Magic: The Gathering judge for Tabletop Simulator. Ask rules questions in chat and get accurate rulings backed by the MTG Comprehensive Rules, Scryfall card data, and Claude AI.

## How It Works

```
TTS Lua Mod  →  FastAPI Server  →  Context Agent (Scryfall + Rules DB + Web Fallback)
     ↑                                    ↓
     ←←←←←←←←←←←←←←←←←←←←←←←  Judge Agent (Claude API)  →  Ruling broadcast to all players
```

1. A player types `judge Can I Lightning Bolt a planeswalker?` in TTS chat
2. The Lua mod scrapes the board state (battlefield, graveyard, exile, hand counts) and sends it to the server
3. The **Context Agent** fetches card data from Scryfall, searches the rules database, and optionally searches Reddit/DuckDuckGo for community rulings
4. The **Judge Agent** sends everything to Claude, which returns a structured ruling with rule citations
5. The ruling is broadcast to all players in TTS chat

### Features

- **Board-aware rulings** — the judge sees what's on every player's battlefield, graveyard, and exile zone
- **Conversation memory** — ask follow-up questions naturally; the server remembers your last 5 exchanges (15-min TTL)
- **Web search fallback** — when the rules DB doesn't have enough context, searches Reddit r/mtgrules and DuckDuckGo
- **Judge Mat UI** — clickable mat on the table for API key setup, no commands needed
- **Per-player API keys** — each player uses their own Anthropic API key, never stored on the server

## Getting Started

### Prerequisites

- Python 3.12+
- An [Anthropic API key](https://console.anthropic.com/)
- Tabletop Simulator (for the Lua mod)

### Local Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Seed the rules database
python scripts/seed_rules.py

# Start the server
python main.py
# Server runs at http://localhost:8080
```

### Running Tests

```bash
# All 92 tests (no API key or network needed)
python -m pytest tests/ -v

# Single module
python -m pytest tests/test_schemas.py -v

# With coverage
python -m pytest tests/ --cov=. --cov-report=term-missing
```

### Smoke Test

```bash
# Against local server
python scripts/test_local.py

# Against deployed server
python scripts/test_local.py https://mtg-judge.fly.dev

# With a live API key (tests actual Claude call)
python scripts/test_local.py http://localhost:8080 sk-ant-your-key-here
```

## TTS Mod Installation

1. Open Tabletop Simulator and load the "Oops I Baked a Pie" 4-player table
2. Right-click each scripting zone and note the GUIDs for each player's battlefield, graveyard, and exile zones
3. Open `lua/judge_mod.lua` and fill in the `ZONE_GUIDS` table with those GUIDs
4. Update `SERVER_URL` to point to your deployed server (or `http://localhost:8080` for local testing)
5. In TTS: **Modding → Scripting → Global**, paste the contents of `lua/judge_mod.lua`, then Save & Play

### Using the Mod

- **Setup**: Click the Judge Mat on the table → paste your Anthropic API key → click Save
- **Ask a question**: Type `judge Can I cast this at instant speed?` in chat
- **Follow-up**: Type `judge What if it has hexproof?` — the judge remembers context
- **Reset session**: Type `judge clear` to start fresh
- **Card references**: Use `[[Card Name]]` brackets for precise card lookups: `judge Can [[Counterspell]] counter [[Abrupt Decay]]?`

## Deployment (Fly.io)

```bash
# Install flyctl: https://fly.io/docs/flyctl/install/
fly auth login
fly apps create mtg-judge
fly deploy

# Verify
curl https://mtg-judge.fly.dev/health
```

The app auto-stops when idle (zero cost) and auto-starts on the next request.

## Project Structure

```
├── main.py                 # FastAPI app entry point
├── routers/judge.py        # POST /judge endpoint
├── agents/
│   ├── context_agent.py    # Gathers cards, rules, web results
│   └── judge_agent.py      # Builds prompt, calls Claude API
├── services/
│   ├── rules_db.py         # SQLite rules search
│   ├── scryfall.py         # Scryfall card API client
│   ├── web_search.py       # Reddit + DuckDuckGo fallback
│   └── session.py          # In-memory session management
├── models/schemas.py       # Pydantic request/response models
├── scripts/
│   ├── seed_rules.py       # Seeds rules database
│   └── test_local.py       # Smoke test script
├── lua/judge_mod.lua       # TTS Lua mod
├── data/                   # Rules DB + comprehensive rules text
├── tests/                  # 92 tests across 8 files
├── Dockerfile
├── fly.toml
└── requirements.txt
```

## API

### `GET /health`
Returns `{"status": "ok"}`.

### `POST /judge`
```json
{
  "question": "Can Lightning Bolt target a planeswalker?",
  "board_state": {
    "player1": {
      "battlefield": ["Lightning Bolt"],
      "graveyard": [],
      "exile": [],
      "hand_count": 6
    }
  },
  "life_totals": {"player1": 20},
  "active_player": "player1",
  "api_key": "sk-ant-...",
  "session_id": "white"
}
```

Response:
```json
{
  "ruling": "Yes, Lightning Bolt can target a planeswalker directly.",
  "explanation": "Since the 2019 rules update, damage spells can target planeswalkers directly...",
  "rules_cited": ["306.7", "115.1a"],
  "cards_referenced": ["Lightning Bolt"],
  "session_id": "white",
  "web_sources": []
}
```
