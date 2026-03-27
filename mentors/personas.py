from dataclasses import dataclass
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


BASE_PROMPT = _load_text(_BASE_DIR / "base_prompt.txt")


@dataclass
class CharacterPersona:
    id: str
    name: str
    symbol: str    # 상징 설명
    target: str    # 대상 사용자
    profile: str   # profiles/{id}.txt 내용


def _load_character(char_id: str, name: str, symbol: str, target: str) -> CharacterPersona:
    profile = _load_text(_BASE_DIR / "profiles" / f"{char_id}.txt")
    return CharacterPersona(id=char_id, name=name, symbol=symbol, target=target, profile=profile)


CHARACTERS: dict[str, CharacterPersona] = {
    "vic": _load_character(
        char_id="vic",
        name="빅 (Vic)",
        symbol="힘과 공격을 상징하는 주황색 캐릭터",
        target="KT 입사를 구체적으로 준비 중인 취준생·경력직",
    ),
    "ddory": _load_character(
        char_id="ddory",
        name="또리 (Ddory)",
        symbol="민첩성과 수비를 상징하는 파란색 캐릭터",
        target="KT라는 회사에 관심이 생긴 대학생·탐색 단계 취준생",
    ),
}
