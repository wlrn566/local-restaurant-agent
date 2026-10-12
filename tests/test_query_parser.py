from app.query_parser import build_search_query, fallback_parse, is_area_missing


def test_fallback_parse_area_and_food():
    parsed = fallback_parse("성수동 파스타 맛집 알려줘")

    assert parsed.area == "성수동"
    assert parsed.food == "파스타"
    assert not is_area_missing(parsed)


def test_fallback_parse_conditions():
    parsed = fallback_parse("강남역 혼밥 점심 추천")

    assert parsed.area == "강남역"
    assert parsed.food == "음식점"
    assert "혼밥" in parsed.conditions
    assert "점심" in parsed.conditions


def test_build_search_query():
    parsed = fallback_parse("제주공항 근처 고기국수 맛집")

    assert build_search_query(parsed, "ignored") == "제주공항 고기국수"


def test_fallback_parse_nearby_restaurants_without_food():
    message = "양재역 근처 맛집을 찾아줘"
    parsed = fallback_parse(message)

    assert parsed.area == "양재역"
    assert "근처" in parsed.conditions
    assert build_search_query(parsed, message) == "양재역 맛집"
