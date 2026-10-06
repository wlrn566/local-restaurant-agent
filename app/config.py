from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@dataclass(frozen=True)
class Settings:
    naver_client_id: str = os.getenv("NAVER_CLIENT_ID", "")
    naver_client_secret: str = os.getenv("NAVER_CLIENT_SECRET", "")
    naver_api_hub_client_id: str = os.getenv("NAVER_API_HUB_CLIENT_ID", "")
    naver_api_hub_client_secret: str = os.getenv("NAVER_API_HUB_CLIENT_SECRET", "")
    naver_maps_client_id: str = os.getenv("NAVER_MAPS_CLIENT_ID", "")
    naver_maps_client_secret: str = os.getenv("NAVER_MAPS_CLIENT_SECRET", "")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "8"))
    log_prompts: bool = os.getenv("LOG_PROMPTS", "false").lower() in {"1", "true", "yes", "on"}

    @property
    def has_naver_search_keys(self) -> bool:
        return bool(self.naver_search_client_id and self.naver_search_client_secret)

    @property
    def naver_search_client_id(self) -> str:
        return self.naver_api_hub_client_id or self.naver_maps_client_id or self.naver_client_id

    @property
    def naver_search_client_secret(self) -> str:
        return self.naver_api_hub_client_secret or self.naver_maps_client_secret or self.naver_client_secret

    @property
    def has_naver_maps_keys(self) -> bool:
        return bool(self.naver_maps_client_id and self.naver_maps_client_secret)


settings = Settings()
