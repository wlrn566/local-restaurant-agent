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
          * { box-sizing: border-box; }
          html, body { height: 100%; margin: 0; }
          body { color: #202124; font-family: system-ui, -apple-system, sans-serif; background: #fff; }
          .app { display: grid; grid-template-columns: minmax(340px, .9fr) minmax(420px, 1.1fr); height: 100dvh; }
          .chat { display: flex; min-height: 0; flex-direction: column; border-right: 1px solid #e5e7eb; }
          header { padding: 20px 24px; border-bottom: 1px solid #e5e7eb; }
          h1 { margin: 0; font-size: 18px; font-weight: 650; }
          .messages { flex: 1; overflow-y: auto; padding: 24px; }
          .intro { max-width: 460px; margin: 18vh auto 0; color: #62676f; text-align: center; }
          .intro h2 { margin: 0 0 8px; color: #202124; font-size: 22px; }
          .message { max-width: 86%; margin: 0 0 18px; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
          .message.user { margin-left: auto; padding: 11px 15px; border-radius: 18px 18px 4px 18px; background: #f1f3f5; }
          .message.assistant { padding: 4px 2px; }
          .message.error { color: #b42318; }
          .restaurant-list { padding: 12px 14px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; }
          .restaurant-list-title { margin: 0 0 8px; color: #62676f; font-size: 13px; }
          .restaurant-list ol { display: grid; gap: 7px; margin: 0; padding-left: 25px; }
          .restaurant-list li { padding-left: 2px; }
          .restaurant-list li strong { font-size: 14px; }
          .restaurant-list li small { display: block; margin-top: 1px; font-size: 12px; }
          .loading { display: flex; align-items: center; gap: 10px; color: #62676f; }
          .spinner { width: 16px; height: 16px; border: 2px solid #d9dde2; border-top-color: #03a84e; border-radius: 50%; animation: spin .8s linear infinite; }
          @keyframes spin { to { transform: rotate(360deg); } }
          .composer-wrap { padding: 16px 20px 20px; border-top: 1px solid #e5e7eb; }
          form { display: flex; align-items: flex-end; gap: 10px; max-width: 760px; margin: auto; padding: 8px 8px 8px 16px; border: 1px solid #d7dbe0; border-radius: 18px; background: white; box-shadow: 0 2px 8px #2021240d; }
          textarea { flex: 1; min-height: 42px; max-height: 140px; resize: vertical; border: 0; outline: 0; padding: 10px 0; font: inherit; }
          button { width: 42px; height: 42px; flex: 0 0 42px; border: 0; border-radius: 13px; color: white; background: #03a84e; font-size: 20px; cursor: pointer; }
          button:disabled { opacity: .5; cursor: wait; }
          .results { min-height: 0; overflow-y: auto; padding: 24px clamp(20px, 4vw, 48px); background: #fafbfc; }
          .results h2 { margin: 0 0 5px; font-size: 20px; }
          .results-caption { margin: 0 0 20px; color: #697079; font-size: 14px; }
          .empty { display: grid; min-height: 100%; place-content: center; color: #697079; text-align: center; }
          .empty strong { margin-bottom: 6px; color: #363a40; font-size: 16px; }
          article { padding: 17px 0; border-top: 1px solid #e2e5e9; }
          article:first-of-type { border-top: 0; }
          article strong { font-size: 16px; }
          small { color: #697079; }
          article p { margin: 8px 0; line-height: 1.5; }
          .address { color: #697079; font-size: 14px; }
          .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
          .actions a { display: inline-flex; align-items: center; min-height: 38px; padding: 0 13px; border-radius: 6px; text-decoration: none; font-size: 14px; font-weight: 600; }
          .reserve { color: white; background: #03c75a; }
          .map { color: #25282d; background: #edf0f2; }
          .notice { margin: 14px 0 0; color: #697079; font-size: 12px; }
          @media (max-width: 760px) {
            html, body { height: auto; min-height: 100%; }
            .app { display: flex; height: auto; min-height: 100dvh; flex-direction: column; }
            .chat { height: min(72dvh, 700px); min-height: 480px; border-right: 0; border-bottom: 1px solid #e5e7eb; }
            header { padding: 16px 18px; }
            .messages { padding: 18px; }
            .intro { margin-top: 12vh; }
            .composer-wrap { padding: 12px; }
            .results { overflow: visible; padding: 22px 20px 36px; }
            .empty { min-height: 180px; }
          }
        </style>
      </head>
      <body>
        <main class="app">
          <section class="chat" aria-label="대화">
            <header><h1>맛집 추천 에이전트</h1></header>
            <div id="messages" class="messages" aria-live="polite">
              <div class="intro" id="intro"><h2>어디에서 뭐 먹을까요?</h2><div>지역과 음식, 원하는 조건을 편하게 말해 주세요.</div></div>
            </div>
            <div class="composer-wrap">
              <form id="form">
                <textarea id="message" rows="1" placeholder="예: 성수동에서 조용한 파스타집 찾아줘" aria-label="메시지 입력"></textarea>
                <button id="send" type="submit" aria-label="메시지 보내기" title="보내기">↑</button>
              </form>
            </div>
          </section>
          <aside id="results" class="results" aria-label="맛집 목록">
            <div class="empty"><strong>추천 맛집</strong><span>검색 결과가 여기에 표시됩니다.</span></div>
          </aside>
        </main>
        <script>
          const form = document.querySelector("#form");
          const messages = document.querySelector("#messages");
          const results = document.querySelector("#results");
          const input = document.querySelector("#message");
          const send = document.querySelector("#send");
          let recentItems = [];
          let reservationStep = null;
          let selectedRestaurant = null;
          let reservationDetails = { date: null, time: null, party: null };
          const escapeHtml = (value) => String(value || "").replace(/[&<>"']/g, (char) => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
          })[char]);
          const addMessage = (text, role) => {
            document.querySelector("#intro")?.remove();
            const node = document.createElement("div");
            node.className = `message ${role}`;
            node.textContent = text;
            messages.append(node);
            messages.scrollTop = messages.scrollHeight;
          };
          const addRestaurantList = (items) => {
            document.querySelector("#intro")?.remove();
            const node = document.createElement("div");
            node.className = "message assistant restaurant-list";
            const title = document.createElement("p");
            title.className = "restaurant-list-title";
            title.textContent = `추천 맛집 ${items.length}곳`;
            const list = document.createElement("ol");
            items.forEach((item) => {
              const row = document.createElement("li");
              const name = document.createElement("strong");
              name.textContent = item.name;
              row.append(name);
              if (item.category) {
                const category = document.createElement("small");
                category.textContent = item.category;
                row.append(category);
              }
              list.append(row);
            });
            node.append(title, list);
            messages.append(node);
            messages.scrollTop = messages.scrollHeight;
          };
          const addReservationLink = (item) => {
            const node = document.createElement("div");
            node.className = "message assistant";
            node.textContent = `${item.name}의 네이버 지도에서 예약 가능 여부를 확인해 주세요.`;
            const url = /^https:\/\/map\.naver\.com\//.test(item.mapUrl || "") ? item.mapUrl : null;
            if (url) {
              const link = document.createElement("a");
              link.className = "reserve";
              link.href = url;
              link.target = "_blank";
              link.rel = "noopener noreferrer";
              link.textContent = "예약하기";
              link.style.cssText = "display:inline-flex;align-items:center;min-height:38px;padding:0 13px;border-radius:6px;color:white;text-decoration:none;font-size:14px;font-weight:600";
              node.append(document.createElement("br"), link);
            }
            messages.append(node);
            messages.scrollTop = messages.scrollHeight;
          };
          const normalizeName = (value) => value.toLocaleLowerCase().replace(/[^가-힣a-z0-9]/g, "");
          const findSelectedRestaurants = (message) => {
            const query = normalizeName(message);
            if (query.length < 2) return [];
            return recentItems.filter((item) => {
              const name = normalizeName(item.name);
              return name.includes(query) || query.includes(name);
            });
          };
          const isRecommendationRequest = (message) => /(맛집|식당|추천|찾아|먹을|근처|주변|파스타|초밥|스시|회|고기|국밥|라멘|피자|버거|치킨|삼겹살|카페|역|동|구)/.test(message);
          const updateReservationDetails = (message) => {
            const date = message.match(/(오늘|내일|모레|\d{4}[./-]\s*\d{1,2}[./-]\s*\d{1,2}|\d{1,2}\s*월\s*\d{1,2}\s*일)/);
            const time = message.match(/((?:오전|오후)\s*\d{1,2}\s*시(?:\s*\d{1,2}\s*분)?|\d{1,2}:\d{2}|\d{1,2}\s*시)/);
            const party = message.match(/(\d+)\s*(?:명|인)/);
            if (date) reservationDetails.date = date[0];
            if (time) reservationDetails.time = time[0];
            if (party) reservationDetails.party = `${party[1]}명`;
            const missing = [];
            if (!reservationDetails.date) missing.push("날짜");
            if (!reservationDetails.time) missing.push("시간");
            if (!reservationDetails.party) missing.push("인원");
            if (missing.length) {
              addMessage(`${missing.join(", ")} 정보가 필요해요. 예: 10월 12일 오후 7시, 2명`, "assistant");
              return;
            }
            reservationStep = null;
            addMessage(`${selectedRestaurant.name} 예약 정보: ${reservationDetails.date}, ${reservationDetails.time}, ${reservationDetails.party}. 네이버 지도에서 예약 가능 여부와 연락처를 확인해 주세요.`, "assistant");
            addReservationLink(selectedRestaurant);
          };
          const handleReservationReply = (message) => {
            if (reservationStep && isRecommendationRequest(message)) {
              reservationStep = null;
              return false;
            }
            if (reservationStep === "details") {
              updateReservationDetails(message);
              return true;
            }
            const selectedMatches = findSelectedRestaurants(message);
            if (selectedMatches.length === 1) {
              const selected = selectedMatches[0];
              selectedRestaurant = selected;
              reservationDetails = { date: null, time: null, party: null };
              reservationStep = "details";
              updateReservationDetails(message);
              return true;
            }
            if (selectedMatches.length > 1) {
              addMessage(`가게를 하나로 정하지 못했어요. ${selectedMatches.map((item) => item.name).join(", ")} 중 정확한 이름을 입력해 주세요.`, "assistant");
              return true;
            }
            if (reservationStep === "select") {
              if (/^(아니요|아니|괜찮아요|예약 안)/.test(message.trim())) {
                reservationStep = null;
                addMessage("알겠습니다. 오른쪽 목록에서 식당 정보를 확인하실 수 있어요.", "assistant");
              } else {
                addMessage("목록에 표시된 가게 이름이나 이름 일부를 입력해 주세요. 새 맛집을 찾으려면 지역이나 음식도 함께 알려주세요.", "assistant");
              }
              return true;
            }
            return false;
          };
          const showLoading = () => {
            const node = document.createElement("div");
            node.id = "loading";
            node.className = "message assistant loading";
            node.innerHTML = '<span class="spinner" aria-hidden="true"></span><span>맛집을 찾고 있어요...</span>';
            messages.append(node);
            messages.scrollTop = messages.scrollHeight;
          };
          const showResults = (data) => {
            const cards = data.items.map((item) => {
              const mapUrl = /^https:\/\/map\.naver\.com\//.test(item.mapUrl || "") ? item.mapUrl : "#";
              return `<article>
                <strong>${escapeHtml(item.name)}</strong><br />
                <small>${escapeHtml(item.category)}</small>
                <p>${escapeHtml(item.reason)}</p>
                <p class="address">${escapeHtml(item.roadAddress || item.address)}</p>
                <div class="actions">
                  <a class="reserve" href="${escapeHtml(mapUrl)}" target="_blank" rel="noopener noreferrer">예약하기</a>
                  <a class="map" href="${escapeHtml(mapUrl)}" target="_blank" rel="noopener noreferrer">네이버 지도</a>
                </div>
              </article>`;
            }).join("");
            results.innerHTML = `<h2>${escapeHtml(data.area || "")}${data.food ? ` ${escapeHtml(data.food)}` : ""} 추천 맛집</h2>
              <p class="results-caption">${data.items.length}곳을 찾았습니다.</p>${cards || '<p>검색 결과가 없습니다.</p>'}
              <p class="notice">예약하기를 누르면 네이버 지도에서 예약 가능 여부를 확인할 수 있습니다.</p>`;
          };
          form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const message = input.value.trim();
            if (!message || send.disabled) return;
            addMessage(message, "user");
            input.value = "";
            if (reservationStep && handleReservationReply(message)) return;
            send.disabled = true;
            showLoading();
            try {
              const response = await fetch("/api/recommend", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message, limit: 5 })
              });
              const data = await response.json();
              document.querySelector("#loading")?.remove();
              if (!response.ok) {
                const detail = typeof data.detail === "object" ? data.detail.detail : data.detail;
                addMessage(detail || "요청을 처리하지 못했습니다. 다시 시도해 주세요.", "assistant error");
                return;
              }
              recentItems = data.items;
              if (recentItems.length === 0) {
                reservationStep = null;
                addMessage("요청하신 지역에서 맛집 목록을 찾지 못했어요. 다른 지역이나 역으로 다시 찾아드릴까요?", "assistant");
              } else {
                reservationStep = "select";
                addRestaurantList(recentItems);
                addMessage("예약하려는 가게 이름을 입력해 주세요. 다른 맛집을 찾고 싶으면 새 요청을 입력하시면 됩니다.", "assistant");
              }
              showResults(data);
            } catch (error) {
              document.querySelector("#loading")?.remove();
              addMessage("서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.", "assistant error");
            } finally {
              send.disabled = false;
              input.focus();
            }
          });
          input.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              form.requestSubmit();
            }
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
