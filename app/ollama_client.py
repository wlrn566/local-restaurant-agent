import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from app.config import Settings
from app.schemas import ParsedQuery


logger = logging.getLogger("restaurant_agent.ollama")


class OllamaClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.ollama_base_url.rstrip("/")

    async def parse_query(self, message: str) -> Optional[ParsedQuery]:
        prompt = (
            "사용자 문장에서 맛집 검색에 필요한 정보를 JSON만으로 추출하세요. "
            "스키마: {\"area\": string|null, \"food\": string|null, "
            "\"conditions\": string[], \"sort_intent\": string}. "
            "지역은 동/역/구/도시/랜드마크를 포함할 수 있습니다. "
            "음식 종류가 없으면 food는 null로 두세요."
        )
        content = await self._chat(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": message},
            ],
            temperature=0.0,
        )
        if not content:
            return None

        data = _extract_json_object(content)
        if not data:
            return None

        return ParsedQuery(
            area=data.get("area"),
            food=data.get("food") or "음식점",
            conditions=data.get("conditions") or [],
            sort_intent=data.get("sort_intent") or "balanced",
        )

    async def write_recommendation_message(self, query: str, items: List[Dict[str, Any]]) -> Optional[str]:
        if not items:
            return None

        compact_items = [
            {
                "name": item.get("name"),
                "category": item.get("category"),
                "address": item.get("roadAddress") or item.get("address"),
                "reason": item.get("reason"),
            }
            for item in items[:5]
        ]
        content = await self._chat(
            [
                {
                    "role": "system",
                    "content": (
                        "맛집 추천 에이전트입니다. 과장하지 말고 검색 결과에 근거해 "
                        "한국어로 짧고 자연스럽게 답하세요. 없는 평점/리뷰 정보는 만들지 마세요."
                    ),
                },
                {
                    "role": "user",
                    "content": f"사용자 요청: {query}\n추천 후보 JSON: {json.dumps(compact_items, ensure_ascii=False)}",
                },
            ],
            temperature=0.4,
        )
        return content.strip() if content else None

    async def _chat(self, messages: List[Dict[str, str]], temperature: float) -> Optional[str]:
        payload = {
            "model": self.settings.ollama_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if self.settings.log_prompts:
            logger.info(
                "ollama.request model=%s temperature=%s messages=%s",
                self.settings.ollama_model,
                temperature,
                json.dumps(messages, ensure_ascii=False),
            )
        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.info("ollama.request_failed error_type=%s error=%r", type(exc).__name__, exc)
            return None

        body = response.json()
        message = body.get("message") or {}
        content = message.get("content")
        if self.settings.log_prompts:
            logger.info("ollama.response content=%r", content)
        return content


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None

    if candidate is None:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            candidate = text[start : end + 1]

    if not candidate:
        return None

    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
