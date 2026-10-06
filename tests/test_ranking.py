from app.ranking import rank_restaurants
from app.schemas import ParsedQuery


def test_rank_restaurants_applies_limit_and_keyword_score():
    parsed = ParsedQuery(area="성수동", food="파스타", conditions=[])
    items = [
        {
            "name": "성수 파스타",
            "category": "음식점>이탈리아음식",
            "address": "서울 성동구",
            "roadAddress": "서울 성동구",
            "searchRank": 2,
            "lat": None,
            "lon": None,
            "mapUrl": "https://map.naver.com",
        },
        {
            "name": "성수 밥집",
            "category": "음식점>한식",
            "address": "서울 성동구",
            "roadAddress": "서울 성동구",
            "searchRank": 1,
            "lat": None,
            "lon": None,
            "mapUrl": "https://map.naver.com",
        },
    ]

    ranked = rank_restaurants(items, parsed, None, 1)

    assert len(ranked) == 1
    assert ranked[0]["name"] == "성수 파스타"
    assert ranked[0]["score"] > 0


def test_rank_restaurants_distance_is_added_when_coords_exist():
    parsed = ParsedQuery(area="성수동", food="음식점", conditions=[])
    items = [
        {
            "name": "가까운 식당",
            "category": "음식점",
            "address": "서울",
            "roadAddress": "서울",
            "searchRank": 1,
            "lat": 37.5445,
            "lon": 127.0557,
            "mapUrl": "https://map.naver.com",
        }
    ]

    ranked = rank_restaurants(items, parsed, (37.5445, 127.0557), 5)

    assert ranked[0]["distanceMeters"] == 0
    assert "기준 지역" in ranked[0]["reason"]
