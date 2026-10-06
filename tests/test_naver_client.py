from urllib.parse import unquote_plus

from app.naver_client import _normalize_local_item


def test_map_url_uses_road_address_only():
    item = _normalize_local_item(
        {
            "title": "<b>성수 파스타</b>",
            "category": "음식점>이탈리아음식",
            "address": "서울 성동구 성수동1가 1",
            "roadAddress": "서울 성동구 왕십리로 1",
            "mapx": "127.0557",
            "mapy": "37.5445",
        },
        0,
    )

    decoded_url = unquote_plus(item["mapUrl"])
    assert decoded_url.endswith("/서울 성동구 왕십리로 1")
    assert "성수 파스타" not in decoded_url
