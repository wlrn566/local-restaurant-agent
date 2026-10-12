# 구조 문서

이 프로젝트는 FastAPI가 전체 흐름을 제어하고, Ollama와 NAVER API를 기능별 클라이언트로 호출하는 구조입니다.

## 디렉터리 구조

```text
local-restaurant-agent/
  app/
    main.py            # FastAPI 엔드포인트, HTML 채팅 UI, 전체 추천 흐름
    config.py          # .env 로딩과 설정 객체
    schemas.py         # 요청/응답 Pydantic 모델
    ollama_client.py   # Ollama /api/chat 호출
    naver_client.py    # NAVER API HUB 지역 검색, Maps Geocoding
    query_parser.py    # Ollama 실패 시 사용하는 규칙 기반 fallback parser
    ranking.py         # 거리/키워드/검색순위 기반 점수 계산
  tests/               # 단위/API 테스트
  docs/                # 설명 문서
  README.md
  requirements.txt
  pytest.ini
```

## 요청 흐름

```text
POST /api/recommend
→ RecommendRequest 검증
→ OllamaClient.parse_query()
→ fallback_parse(), 필요할 때만
→ is_area_missing()
→ build_search_query()
→ NaverClient.search_local()
→ NaverClient.geocode()
→ rank_restaurants()
→ _public_item()
→ OllamaClient.write_recommendation_message()
→ RecommendResponse 반환
```

브라우저 UI는 `GET /`에서 HTML과 JavaScript로 제공됩니다. JavaScript가 `POST /api/recommend`를 호출하고 응답을 채팅과 오른쪽 식당 목록에 표시합니다. 이 UI의 대화/예약 단계 상태는 브라우저 메모리에만 있으므로 새로고침하면 초기화됩니다.

## 주요 모듈

### `app/main.py`

FastAPI 앱의 진입점입니다.

- `/`: 간단한 HTML 테스트 화면
- `/health`: Ollama 모델명과 NAVER 키 설정 여부 확인
- `/api/recommend`: 추천 API
- `/`의 클라이언트 UI: 채팅, 로딩 표시, 식당 목록, 예약 정보 수집

`recommend()` 함수가 전체 파이프라인을 조율합니다.

웹 UI는 검색 결과가 없으면 채팅으로 없다고 안내합니다. 결과가 있으면 채팅에 번호 목록을 보여주고 가게 이름 선택을 기다립니다. 가게 이름 전체 또는 일부가 후보 하나와 일치하면 예약 정보 수집 단계로 이동합니다. 날짜, 시간, 인원이 모두 입력되어야 지도 링크를 안내하며, 부족한 항목은 다시 묻습니다. 이 정보는 브라우저에서만 수집되고 예약 API로 전송되거나 저장되지 않습니다.

### `app/ollama_client.py`

Ollama의 `/api/chat`을 호출합니다.

- `parse_query()`: 사용자 문장에서 `area`, `food`, `conditions`, `sort_intent`를 JSON으로 추출
- `write_recommendation_message()`: 정렬된 맛집 후보를 바탕으로 한국어 추천 문장 생성
- `_chat()`: 실제 HTTP 호출 공통 함수

Ollama가 꺼져 있거나 응답 파싱에 실패하면 `None`을 반환하고, `main.py`에서 fallback parser로 넘어갑니다.

### `app/naver_client.py`

NAVER API 연동을 담당합니다.

- `search_local()`: NAVER API HUB 지역 검색 호출
- `geocode()`: NAVER Maps Geocoding 호출
- `_normalize_local_item()`: NAVER 응답을 내부 아이템 구조로 정규화
- `_build_naver_map_url()`: 도로명 주소만 사용해 네이버 지도 검색 URL 생성
- `haversine_meters()`: 좌표 간 거리 계산

지역 검색 호출 정보:

```text
GET https://naverapihub.apigw.ntruss.com/search/v1/local
X-NCP-APIGW-API-KEY-ID: ...
X-NCP-APIGW-API-KEY: ...
```

### `app/query_parser.py`

Ollama가 실패했을 때 사용하는 규칙 기반 parser입니다.

- 음식 키워드 사전
- 조건 키워드 사전
- 불필요한 표현 제거
- 지역/음식/조건 추정

정확도는 제한적이므로, 정상 경로에서는 Ollama 파싱 결과를 우선 사용합니다.

### `app/ranking.py`

후보 맛집 점수를 계산합니다.

현재 점수 공식:

```text
score = 검색순위 45% + 키워드 일치 35% + 거리 20%
```

거리 정보가 없으면 거리 점수는 중립값으로 처리합니다.

## 에러와 degraded 동작

- Ollama 실패: fallback parser 또는 기본 추천 문구 사용, `degraded=true`
- NAVER 키 누락: `503 NAVER_CONFIG_MISSING`
- NAVER API 실패: `503 NAVER_API_ERROR`
- 지역 누락: `400 AREA_REQUIRED`
- Geocoding 실패: 추천은 계속 진행하고 warning만 추가
- 검색 성공 후 후보 0개: 빈 목록을 반환하고 UI가 결과 없음 안내

## 현재 한계

- 네이버 공개 지역 검색 결과에는 평점/리뷰 수가 포함되지 않음
- NAVER API HUB 지역 검색 `display` 제한 때문에 한 번에 많은 후보를 가져오지 않음
- fallback 파서는 제한된 키워드 규칙을 사용하므로 자연어의 모든 표현을 이해하지 못함
- 예약 기능은 실제 예약 서비스 API와 연결되어 있지 않음. 날짜·시간·인원 수집 후 네이버 지도 페이지를 열어 사용자가 예약을 마무리함
- 브라우저 대화 상태는 새로고침하면 사라지고 사용자별 저장 기능이 없음
- 응답 캐시, 사용자 선호 저장, 운영용 인증/배포 설정은 없음
