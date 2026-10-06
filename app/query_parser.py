import re
from typing import Iterable

from app.schemas import ParsedQuery


FOOD_WORDS = {
    "파스타",
    "초밥",
    "스시",
    "회",
    "고기국수",
    "국밥",
    "라멘",
    "피자",
    "버거",
    "치킨",
    "삼겹살",
    "고기",
    "한식",
    "중식",
    "일식",
    "양식",
    "카페",
    "디저트",
    "분식",
    "곱창",
    "족발",
    "보쌈",
    "냉면",
    "칼국수",
    "순대",
    "떡볶이",
}

CONDITION_WORDS = {
    "혼밥",
    "데이트",
    "가성비",
    "주차",
    "조용한",
    "술집",
    "점심",
    "저녁",
    "아침",
    "브런치",
    "근처",
    "아이",
    "단체",
}

NOISE_WORDS = {
    "맛집",
    "추천",
    "알려줘",
    "리스트",
    "지역",
    "근처",
    "에서",
    "으로",
    "으로",
    "찾아줘",
    "부탁해",
}


def fallback_parse(message: str) -> ParsedQuery:
    tokens = _tokenize(message)
    food = next((token for token in tokens if token in FOOD_WORDS), None)
    conditions = [token for token in tokens if token in CONDITION_WORDS and token != food]

    area_tokens = [
        token
        for token in tokens
        if token not in FOOD_WORDS
        and token not in CONDITION_WORDS
        and token not in NOISE_WORDS
        and not token.isdigit()
    ]
    area = " ".join(area_tokens[:2]) if area_tokens else None

    if not food:
        food = "음식점"

    return ParsedQuery(area=area, food=food, conditions=conditions)


def build_search_query(parsed: ParsedQuery, original_message: str) -> str:
    parts = [parsed.area, parsed.food]
    parts.extend(parsed.conditions[:2])
    query = " ".join(part for part in parts if part)
    if query:
        return query
    return original_message


def is_area_missing(parsed: ParsedQuery) -> bool:
    return not parsed.area or parsed.area.strip() in {"맛집", "음식점", "추천"}


def _tokenize(message: str) -> Iterable[str]:
    normalized = re.sub(r"[^\w가-힣]+", " ", message)
    return [token.strip() for token in normalized.split() if token.strip()]
