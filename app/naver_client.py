import logging
import math
import re
from urllib.parse import quote_plus
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import Settings


logger = logging.getLogger("restaurant_agent.naver")


class NaverConfigError(RuntimeError):
    pass


class NaverApiError(RuntimeError):
    pass


class NaverClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def search_local(self, query: str, limit: int) -> List[Dict[str, Any]]:
        if not self.settings.has_naver_search_keys:
            raise NaverConfigError(
                "NAVER_API_HUB_CLIENT_ID and NAVER_API_HUB_CLIENT_SECRET are required. "
                "NAVER_MAPS_CLIENT_ID/SECRET are also accepted as a fallback when they are API Gateway keys."
            )

        headers = {
            "X-NCP-APIGW-API-KEY-ID": self.settings.naver_search_client_id,
            "X-NCP-APIGW-API-KEY": self.settings.naver_search_client_secret,
        }
        params = {
            "query": query,
            "display": min(max(limit, 1), 5),
            "start": 1,
            "sort": "comment",
            "format": "json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                response = await client.get(
                    "https://naverapihub.apigw.ntruss.com/search/v1/local",
                    headers=headers,
                    params=params,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.info(
                "naver.search_failed status=%s body=%r",
                exc.response.status_code,
                exc.response.text[:500],
            )
            raise NaverApiError(f"Naver API Hub Local Search returned {exc.response.status_code}.") from exc
        except httpx.HTTPError as exc:
            raise NaverApiError("Naver Search API request failed.") from exc

        return [_normalize_local_item(item, index) for index, item in enumerate(response.json().get("items", []))]

    async def geocode(self, query: str) -> Optional[Tuple[float, float]]:
        if not self.settings.has_naver_maps_keys:
            return None

        headers = {
            "x-ncp-apigw-api-key-id": self.settings.naver_maps_client_id,
            "x-ncp-apigw-api-key": self.settings.naver_maps_client_secret,
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                response = await client.get(
                    "https://maps.apigw.ntruss.com/map-geocode/v2/geocode",
                    headers=headers,
                    params={"query": query},
                )
                response.raise_for_status()
        except httpx.HTTPError:
            return None

        addresses = response.json().get("addresses", [])
        if not addresses:
            return None
        first = addresses[0]
        try:
            return float(first["y"]), float(first["x"])
        except (KeyError, TypeError, ValueError):
            return None


def _normalize_local_item(item: Dict[str, Any], index: int) -> Dict[str, Any]:
    name = _strip_html(item.get("title", ""))
    road_address = item.get("roadAddress") or None
    address = item.get("address") or None
    coords = _coords_from_local_item(item)

    return {
        "name": name,
        "category": item.get("category") or None,
        "address": address,
        "roadAddress": road_address,
        "phone": item.get("telephone") or None,
        "link": item.get("link") or None,
        "mapUrl": _build_naver_map_url(road_address or address),
        "lat": coords[0] if coords else None,
        "lon": coords[1] if coords else None,
        "searchRank": index + 1,
    }


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value).strip()


def _build_naver_map_url(road_address: Optional[str]) -> str:
    query = road_address or ""
    return f"https://map.naver.com/p/search/{quote_plus(query)}"


def _coords_from_local_item(item: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    try:
        mapx = float(item.get("mapx"))
        mapy = float(item.get("mapy"))
    except (TypeError, ValueError):
        return None

    # API Hub returns WGS84 lon/lat strings. The old Open API returned scaled integers.
    candidates = [(mapy, mapx), (mapy / 10_000_000, mapx / 10_000_000)]
    for lat, lon in candidates:
        if 32 <= lat <= 39 and 124 <= lon <= 132:
            return lat, lon
    return None


def haversine_meters(origin: Tuple[float, float], dest: Tuple[float, float]) -> float:
    lat1, lon1 = origin
    lat2, lon2 = dest
    radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))
