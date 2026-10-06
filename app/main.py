import logging
from typing import Any, Dict, List, Union

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import settings
from app.naver_client import NaverApiError, NaverClient, NaverConfigError
from app.ollama_client import OllamaClient
from app.query_parser import build_search_query, fallback_parse, is_area_missing
from app.ranking import rank_restaurants
from app.schemas import ErrorResponse, RecommendRequest, RecommendResponse


logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("restaurant_agent")

app = FastAPI(
    title="Local Restaurant Agent",
    description="FastAPI + Ollama + Naver restaurant recommendation agent.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return """
    <!doctype html>
    <html lang="ko">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>맛집 추천 에이전트</title>
        <style>
          body { font-family: system-ui, -apple-system, sans-serif; max-width: 760px; margin: 40px auto; padding: 0 20px; }
          form { display: flex; gap: 8px; }
          input { flex: 1; padding: 12px; font-size: 16px; }
          button { padding: 12px 16px; font-size: 16px; }
          article { border: 1px solid #ddd; border-radius: 8px; padding: 14px; margin: 12px 0; }
          small { color: #666; }
        </style>
      </head>
      <body>
        <h1>맛집 추천 에이전트</h1>
        <form id="form">
          <input id="message" value="성수동 파스타 맛집 알려줘" />
          <button>검색</button>
        </form>
        <div id="result"></div>
        <script>
          const form = document.querySelector("#form");
          const result = document.querySelector("#result");
          form.addEventListener("submit", async (event) => {
            event.preventDefault();
            result.innerHTML = "검색 중...";
            const response = await fetch("/api/recommend", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ message: document.querySelector("#message").value, limit: 5 })
            });
            const data = await response.json();
            if (!response.ok) {
              const detail = typeof data.detail === "object" ? data.detail.detail : data.detail;
              result.innerHTML = `<p>${detail || "오류가 발생했습니다."}</p>`;
              return;
            }
            result.innerHTML = `<p>${data.message}</p>` + data.items.map((item) => `
              <article>
                <strong>${item.name}</strong><br />
                <small>${item.category || ""}</small>
                <p>${item.reason}</p>
                <p>${item.roadAddress || item.address || ""}</p>
                <a href="${item.mapUrl}" target="_blank" rel="noreferrer">네이버 지도에서 보기</a>
              </article>
            `).join("");
          });
        </script>
      </body>
    </html>
    """


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "ollamaModel": settings.ollama_model,
        "hasNaverSearchKeys": settings.has_naver_search_keys,
        "hasNaverMapsKeys": settings.has_naver_maps_keys,
    }


@app.post(
    "/api/recommend",
    response_model=RecommendResponse,
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def recommend(request: RecommendRequest) -> Union[RecommendResponse, JSONResponse]:
    ollama = OllamaClient(settings)
    naver = NaverClient(settings)
    warnings: List[str] = []

    logger.info("recommend.request message=%r limit=%s", request.message, request.limit)

    parsed = await ollama.parse_query(request.message)
    degraded = parsed is None
    if parsed is None:
        parsed = fallback_parse(request.message)
        warnings.append("Ollama를 사용할 수 없어 규칙 기반 파싱을 사용했습니다.")
        logger.info("recommend.parsed source=fallback parsed=%s", parsed.model_dump())
    else:
        logger.info("recommend.parsed source=ollama parsed=%s", parsed.model_dump())

    if is_area_missing(parsed):
        logger.info("recommend.rejected code=AREA_REQUIRED message=%r", request.message)
        return JSONResponse(
            status_code=400,
            content={
                "detail": "지역을 찾지 못했습니다. 예: '성수동 파스타', '강남역 혼밥'처럼 지역을 포함해 주세요.",
                "code": "AREA_REQUIRED",
            },
        )

    search_query = build_search_query(parsed, request.message)
    logger.info("recommend.search_query query=%r", search_query)
    try:
        candidates = await naver.search_local(search_query, request.limit)
    except NaverConfigError as exc:
        return JSONResponse(
            status_code=503,
            content={"detail": str(exc), "code": "NAVER_CONFIG_MISSING"},
        )
    except NaverApiError as exc:
        return JSONResponse(
            status_code=503,
            content={"detail": str(exc), "code": "NAVER_API_ERROR"},
        )
    logger.info("recommend.naver_candidates count=%s", len(candidates))

    area_coords = await naver.geocode(parsed.area or "")
    if area_coords is None:
        warnings.append("네이버 지도 Geocoding을 사용할 수 없어 거리 점수는 제한적으로 반영했습니다.")

    ranked = rank_restaurants(candidates, parsed, area_coords, request.limit)
    response_items = [_public_item(item) for item in ranked]
    logger.info("recommend.ranked count=%s names=%s", len(response_items), [item["name"] for item in response_items])

    message = await ollama.write_recommendation_message(request.message, response_items)
    if not message:
        degraded = True
        message = _fallback_message(parsed.area, parsed.food, len(response_items))
        warnings.append("Ollama 응답 생성을 사용할 수 없어 기본 안내 문구를 사용했습니다.")

    logger.info("recommend.response degraded=%s warnings=%s", degraded, warnings)
    return RecommendResponse(
        query=request.message,
        area=parsed.area,
        food=parsed.food,
        items=response_items,
        followUpSuggestions=_follow_up_suggestions(parsed.conditions),
        message=message,
        degraded=degraded,
        warnings=warnings,
    )


def _public_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": item["name"],
        "category": item.get("category"),
        "address": item.get("address"),
        "roadAddress": item.get("roadAddress"),
        "phone": item.get("phone"),
        "link": item.get("link"),
        "mapUrl": item.get("mapUrl"),
        "distanceMeters": item.get("distanceMeters"),
        "score": item["score"],
        "reason": item["reason"],
    }


def _fallback_message(area: str, food: str, count: int) -> str:
    return f"{area} 주변 {food or '맛집'} 후보 {count}곳을 찾았습니다. 지도 링크로 위치를 확인해 보세요."


def _follow_up_suggestions(conditions: List[str]) -> List[str]:
    base = ["가성비 좋은 곳", "혼밥하기 좋은 곳", "데이트하기 좋은 곳", "주차 가능한 곳"]
    return [suggestion for suggestion in base if not any(condition in suggestion for condition in conditions)][:3]
