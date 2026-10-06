from typing import Any, Dict, List, Optional, Tuple

from app.naver_client import haversine_meters
from app.schemas import ParsedQuery


def rank_restaurants(
    items: List[Dict[str, Any]],
    parsed: ParsedQuery,
    area_coords: Optional[Tuple[float, float]],
    limit: int,
) -> List[Dict[str, Any]]:
    ranked = []
    for item in items:
        distance = _distance(area_coords, item)
        keyword_score = _keyword_score(item, parsed)
        search_score = _search_score(item.get("searchRank", 999))
        distance_score = _distance_score(distance)

        score = round(search_score * 0.45 + keyword_score * 0.35 + distance_score * 0.20, 4)
        ranked.append(
            {
                **item,
                "distanceMeters": round(distance, 1) if distance is not None else None,
                "score": score,
                "reason": _reason(item, parsed, distance),
            }
        )

    ranked.sort(key=lambda value: value["score"], reverse=True)
    return ranked[:limit]


def _distance(area_coords: Optional[Tuple[float, float]], item: Dict[str, Any]) -> Optional[float]:
    if not area_coords or item.get("lat") is None or item.get("lon") is None:
        return None
    return haversine_meters(area_coords, (item["lat"], item["lon"]))


def _keyword_score(item: Dict[str, Any], parsed: ParsedQuery) -> float:
    haystack = " ".join(
        str(item.get(key) or "") for key in ["name", "category", "address", "roadAddress"]
    ).lower()
    keywords = [parsed.food or "", *parsed.conditions]
    keywords = [keyword.lower() for keyword in keywords if keyword]
    if not keywords:
        return 0.5
    matched = sum(1 for keyword in keywords if keyword in haystack)
    return min(1.0, 0.35 + matched / len(keywords) * 0.65)


def _search_score(rank: int) -> float:
    if rank <= 1:
        return 1.0
    return max(0.0, 1.0 - (rank - 1) * 0.08)


def _distance_score(distance: Optional[float]) -> float:
    if distance is None:
        return 0.5
    if distance <= 300:
        return 1.0
    if distance >= 3000:
        return 0.0
    return 1.0 - ((distance - 300) / 2700)


def _reason(item: Dict[str, Any], parsed: ParsedQuery, distance: Optional[float]) -> str:
    parts = []
    if parsed.food and parsed.food != "음식점":
        parts.append(f"{parsed.food} 검색어와 잘 맞습니다")
    category = item.get("category")
    if category:
        parts.append(f"네이버 분류: {category}")
    if distance is not None:
        parts.append(f"기준 지역에서 약 {int(distance)}m")
    if not parts:
        parts.append("네이버 지역 검색 결과 상위 후보입니다")
    return " · ".join(parts)
