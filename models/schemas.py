from pydantic import BaseModel, field_validator


class PlayerBoardState(BaseModel):
    battlefield: list[str] = []
    graveyard: list[str] = []
    exile: list[str] = []
    hand_count: int = 0


class JudgeRequest(BaseModel):
    question: str
    board_state: dict[str, PlayerBoardState] = {}
    life_totals: dict[str, int] = {}
    active_player: str
    api_key: str
    session_id: str = ""

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be empty")
        return v.strip()


class JudgeResponse(BaseModel):
    ruling: str
    explanation: str
    rules_cited: list[str] = []
    cards_referenced: list[str] = []
    session_id: str = ""
    web_sources: list[str] = []


class ScryfallCard(BaseModel):
    name: str
    oracle_text: str
    type_line: str
    mana_cost: str = ""
    keywords: list[str] = []


class RulesChunk(BaseModel):
    rule_number: str
    rule_text: str
    keywords: list[str] = []
