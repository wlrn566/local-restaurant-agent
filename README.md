# Local Restaurant Agent

지역과 음식 키워드를 입력하면 NAVER API HUB 지역 검색 결과를 바탕으로 맛집 후보를 추천하는 FastAPI 애플리케이션입니다. Ollama의 `qwen3.5:4b`는 사용자 문장 파싱과 추천 문장 생성에 사용합니다.

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
- Ollama 연결 실패 시 규칙 기반 fallback parser 사용
- NAVER API HUB 지역 검색 연동
- NAVER Maps Geocoding 키가 있으면 거리 점수 반영
- 네이버 지도 URL은 업체명이 아니라 도로명 주소만 사용
- 프롬프트/파싱/검색어/랭킹 로그 지원
- 테스트 8개 통과

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

필수 값:

- `NAVER_API_HUB_CLIENT_ID`
- `NAVER_API_HUB_CLIENT_SECRET`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`

선택 값:

- `NAVER_MAPS_CLIENT_ID`, `NAVER_MAPS_CLIENT_SECRET`: Geocoding으로 거리 점수를 더 정확히 계산할 때 사용
- `LOG_PROMPTS=true`: Ollama에 전달되는 system/user 메시지와 응답을 터미널에 출력

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
- [추가 구현 후보](docs/ROADMAP.md)
