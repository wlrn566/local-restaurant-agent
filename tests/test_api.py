from fastapi.testclient import TestClient

from app.main import app
from app.naver_client import NaverConfigError
from app.schemas import ParsedQuery


client = TestClient(app)


def test_recommend_returns_controlled_error_when_naver_keys_missing(monkeypatch):
    async def fake_parse_query(self, message):
        return ParsedQuery(area="성수동", food="파스타", conditions=[])

    async def fake_search_local(self, query, limit):
        raise NaverConfigError("NAVER_API_HUB_CLIENT_ID and NAVER_API_HUB_CLIENT_SECRET are required.")

    monkeypatch.setattr("app.ollama_client.OllamaClient.parse_query", fake_parse_query)
    monkeypatch.setattr("app.naver_client.NaverClient.search_local", fake_search_local)

    response = client.post("/api/recommend", json={"message": "성수동 파스타", "limit": 5})

    assert response.status_code == 503
    assert response.json()["code"] == "NAVER_CONFIG_MISSING"


def test_recommend_asks_for_area_when_missing(monkeypatch):
    async def fake_parse_query(self, message):
        return ParsedQuery(area=None, food="파스타", conditions=[])

    monkeypatch.setattr("app.ollama_client.OllamaClient.parse_query", fake_parse_query)

    response = client.post("/api/recommend", json={"message": "파스타 맛집", "limit": 5})

    assert response.status_code == 400
    assert response.json()["code"] == "AREA_REQUIRED"
