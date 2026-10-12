# Local Restaurant Agent

지역과 음식 키워드를 입력하면 NAVER API HUB 검색 결과에서 맛집 후보를 보여주는 FastAPI 애플리케이션입니다. Ollama의 `qwen3.5:4b`가 켜져 있으면 사용자 요청 파싱과 추천 문장 생성에 사용하고, 꺼져 있으면 규칙 기반 파서와 기본 문장으로 계속 동작합니다.

현재 구현은 복잡한 agent tool loop가 아니라, 동작이 예측 가능한 추천 파이프라인입니다.

```text
사용자 입력
→ Ollama로 지역/음식/조건 파싱
→ NAVER API HUB 지역 검색
→ 선택적으로 NAVER Maps Geocoding
→ 거리/키워드/검색 순위 기반 랭킹
→ Ollama로 추천 문장 생성
→ FastAPI 응답
```

## 현재 구현 상태

- `GET /`: 브라우저에서 바로 테스트할 수 있는 간단한 웹 UI
- `GET /health`: 설정 상태 확인
- `POST /api/recommend`: 맛집 추천 API
- 채팅형 웹 UI: 대화는 왼쪽에 쌓이고 추천 식당은 오른쪽 목록에 표시
- 예약 대화: 추천 식당 이름 선택 후 날짜·시간·인원 확인, 해당 식당의 네이버 지도 열기
- Ollama 연결 실패 시 규칙 기반 fallback parser 사용
- NAVER API HUB 지역 검색 연동
- NAVER Maps Geocoding 키가 있으면 거리 점수 반영
- 네이버 지도 URL은 업체명이 아니라 도로명 주소만 사용
- 프롬프트/파싱/검색어/랭킹 로그 지원

예약 대화는 날짜·시간·인원을 모아 네이버 지도 링크로 안내하는 단계입니다. 예약 사이트와 연결해 예약을 제출하거나 예약을 확정하는 기능은 아직 없습니다.

## 설치

```bash
cd /Users/yonghee/dev/codex/local-restaurant-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

이미 `.venv`가 있으면 새로 만들 필요 없이 활성화만 하면 됩니다.

```bash
source .venv/bin/activate
```

## 환경 변수

`.env`에 아래 값을 설정합니다.

```env
NAVER_API_HUB_CLIENT_ID=...
NAVER_API_HUB_CLIENT_SECRET=...

NAVER_MAPS_CLIENT_ID=...
NAVER_MAPS_CLIENT_SECRET=...

OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:4b
REQUEST_TIMEOUT_SECONDS=8
LOG_PROMPTS=false
```

맛집 검색에 필요한 값:

- `NAVER_API_HUB_CLIENT_ID`
- `NAVER_API_HUB_CLIENT_SECRET`

선택 값:

- `OLLAMA_BASE_URL`, `OLLAMA_MODEL`: 로컬 Ollama 모델 사용. Ollama가 없어도 fallback으로 검색 가능
- `NAVER_MAPS_CLIENT_ID`, `NAVER_MAPS_CLIENT_SECRET`: Geocoding으로 거리 점수를 더 정확히 계산할 때 사용
- `LOG_PROMPTS=true`: Ollama에 전달되는 system/user 메시지와 응답을 터미널에 출력

기존 설정과의 호환을 위해 검색 키는 `NAVER_API_HUB_CLIENT_ID/SECRET`을 우선 사용하며, 비어 있으면 `NAVER_MAPS_CLIENT_ID/SECRET`, 그 다음 `NAVER_CLIENT_ID/SECRET`을 검색 키로 사용합니다. NAVER Maps Geocoding은 `NAVER_MAPS_CLIENT_ID/SECRET`만 사용합니다.

## Ollama 실행

다른 터미널에서 Ollama 서버를 켭니다.

```bash
ollama serve
```

모델이 설치되어 있는지 확인합니다.

```bash
ollama list
```

`qwen3.5:4b`가 없으면 설치합니다.

```bash
ollama pull qwen3.5:4b
```

## FastAPI 실행

```bash
cd /Users/yonghee/dev/codex/local-restaurant-agent
source .venv/bin/activate
uvicorn app.main:app --reload
```

가상환경을 활성화하지 않고 직접 실행할 수도 있습니다.

```bash
.venv/bin/uvicorn app.main:app --reload
```

브라우저에서 확인:

- 웹 UI: http://127.0.0.1:8000
- Swagger UI: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

## API 사용 예시

```bash
curl -X POST http://127.0.0.1:8000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"message":"성수동 파스타 맛집 알려줘","limit":5}'
```

응답 예시:

```json
{
  "query": "성수동 파스타 맛집 알려줘",
  "area": "성수동",
  "food": "파스타",
  "items": [
    {
      "name": "가게명",
      "category": "음식점>이탈리아음식",
      "roadAddress": "서울 성동구 ...",
      "mapUrl": "https://map.naver.com/p/search/...",
      "distanceMeters": 420.3,
      "score": 0.91,
      "reason": "파스타 검색어와 잘 맞습니다 · 네이버 분류: 음식점>이탈리아음식"
    }
  ],
  "followUpSuggestions": ["가성비 좋은 곳", "혼밥하기 좋은 곳", "데이트하기 좋은 곳"],
  "message": "성수동 파스타 후보를 찾았습니다...",
  "degraded": false,
  "warnings": []
}
```

`POST /api/recommend`는 요청마다 독립적으로 동작하는 검색 API입니다. 채팅 UI의 대화 상태와 예약 정보 수집은 브라우저 안에서 관리하며 서버 세션이나 데이터베이스에는 저장하지 않습니다.

## 웹 채팅 사용 흐름

1. 지역과 음식 또는 조건을 입력합니다. 예: `양재역 근처 맛집`, `성수동 조용한 파스타`
2. 검색 중 표시가 나온 뒤, 검색 결과가 오른쪽 목록에 표시되고 채팅에는 가게 이름이 번호 목록으로 나옵니다.
3. 예약하려는 가게 이름 전체 또는 일부를 입력합니다. 이름이 겹쳐 여러 곳이 선택되면 정확한 이름을 다시 요청합니다.
4. 예약 날짜, 시간, 인원을 입력합니다. 빠진 값이 있으면 필요한 항목을 다시 묻습니다.
5. 입력한 예약 정보를 확인한 뒤 네이버 지도 링크를 엽니다. 실제 예약 가능 시간과 연락처 입력, 예약 제출은 네이버 지도에서 진행해야 합니다.

예약 단계 중 새 지역이나 음식으로 다시 검색하면 새 추천 목록부터 같은 흐름을 시작합니다. 검색 결과가 없으면 채팅에서 결과가 없다고 안내하고 예약 단계로 넘어가지 않습니다.

## 로그 확인

기본 로그:

- 사용자 입력
- Ollama 파싱 결과 또는 fallback 여부
- NAVER 검색어
- 후보 개수
- 최종 랭킹 결과
- degraded/warnings

프롬프트까지 보고 싶으면 `.env`에서 켭니다.

```env
LOG_PROMPTS=true
```

서버를 재시작하면 터미널에 Ollama 요청/응답이 출력됩니다.

## 테스트

```bash
cd /Users/yonghee/dev/codex/local-restaurant-agent
source .venv/bin/activate
pytest -q
```

또는:

```bash
.venv/bin/pytest -q
```

## 문제 해결

`uvicorn: command not found`

가상환경을 활성화하지 않은 상태입니다.

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

Ollama 로그에 `request_failed`가 찍힘

Ollama 서버가 꺼져 있거나 `OLLAMA_BASE_URL`이 다릅니다.

```bash
ollama serve
curl http://127.0.0.1:11434/api/tags
```

NAVER API가 `401 Unauthorized`를 반환함

API HUB 지역 검색용 키가 아니거나, API Gateway 헤더용 키가 잘못된 상태입니다. `.env`의 `NAVER_API_HUB_CLIENT_ID`, `NAVER_API_HUB_CLIENT_SECRET` 값을 확인하세요.

지역을 찾지 못했다는 응답이 나옴

입력에 명확한 지역명을 포함하세요.

```text
성수동 파스타
강남역 혼밥
해운대 회
제주공항 근처 고기국수
```

## 추가 문서

- [구조 문서](docs/ARCHITECTURE.md)
- [구현 현황과 다음 작업](docs/ROADMAP.md)
