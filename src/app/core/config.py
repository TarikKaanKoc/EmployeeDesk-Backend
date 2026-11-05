"""Application settings.

One flat set of environment variables (the `.env` the API and the scripts
share), read once into `settings`. Grouped by the part of the system each
field configures. Nothing is validated at import; `assert_production_ready`
is called by the API at startup.
"""

import secrets
from pathlib import Path
from typing import List, Optional, Set

from loguru import logger
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Where a development process keeps the signing key it generated for
#: itself, so a `--reload` restart does not sign everyone out. Git-ignored.
DEV_SECRET_FILE = Path(__file__).resolve().parents[3] / ".dev-jwt-secret"


def csv(raw: Optional[str]) -> List[str]:
    """A comma-separated setting as a list, blanks dropped."""
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def _local(url: str) -> bool:
    return "localhost" in url or "127.0.0.1" in url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- app ---
    APP_NAME: str = "employeedesk-api"
    APP_TITLE: str = "EmployeeDesk API"
    APP_DESCRIPTION: str = "Bilingual HR and procurement assistant"
    APP_VERSION: str = "0.0.1"
    DEBUG: bool = False
    DEFAULT_LANGUAGE: str = "en"
    ALLOWED_HOSTS: Optional[str] = None
    CORS_ORIGINS: Optional[str] = None
    #: Proxies whose `X-Forwarded-For` is believed (CIDR-free list of addresses).
    TRUSTED_PROXY_IPS: Optional[str] = None
    MAX_REQUEST_BYTES: int = 2 * 1024 * 1024
    #: Off only in the test suite, which logs in far more than ten times a
    #: minute. Refused in production by `assert_production_ready`.
    RATE_LIMITING: bool = True

    # --- database ---
    DATABASE_URL: str = (
        "postgresql+asyncpg://employeedesk:employeedesk@127.0.0.1:5433/employeedesk"
    )
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 5

    # --- redis ---
    REDIS_URL: str = "redis://127.0.0.1:6380/0"
    # How many copies of the API run behind the load balancer. Only the
    # memory:// store cares: it cannot be shared, so it is refused above 1.
    REPLICAS: int = 1

    # --- auth ---
    JWT_SECRET_KEY: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- azure openai ---
    #: Azure AI Foundry project endpoint, OpenAI-compatible:
    #: https://<resource>.services.ai.azure.com/openai/v1 (the resource-level
    #: path: the project-scoped one serves chat but not embeddings)
    AZURE_OPENAI_BASE_URL: Optional[str] = None
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_CHAT_DEPLOYMENT: str = "gpt-5.4-mini"
    #: Reasoning budget for models that take one (gpt-5 family). "minimal"
    #: keeps the assistant's turn fast; the tools do the thinking.
    AZURE_OPENAI_REASONING_EFFORT: str = "minimal"
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = "text-embedding-3-small"
    #: Column width of `policy_clauses.embedding`. Changing it is a migration.
    EMBEDDING_DIMENSIONS: int = 1536
    #: A hit with no keyword match must reach this cosine similarity to count.
    #: Tuned on the synthetic corpus: relevant paraphrases score 0.29 to 0.54,
    #: unrelated questions 0.15 to 0.30; the overlap is left to the model gate
    #: below (it answers [NO_POLICY_ANSWER] when a clause does not fit). It is
    #: the second gate; this one keeps noise out of what it sees.
    POLICY_MIN_VECTOR_SCORE: float = 0.28

    # --- mock erp ---
    MOCK_ERP_URL: str = "http://127.0.0.1:8013"

    @property
    def allowed_hosts(self) -> List[str]:
        return csv(self.ALLOWED_HOSTS)

    @property
    def allowed_origins(self) -> List[str]:
        return csv(self.CORS_ORIGINS)

    @property
    def trusted_proxy_ips(self) -> Set[str]:
        return set(csv(self.TRUSTED_PROXY_IPS))

    @property
    def llm_configured(self) -> bool:
        return bool(self.AZURE_OPENAI_BASE_URL and self.AZURE_OPENAI_API_KEY)

    @property
    def embeddings_configured(self) -> bool:
        return self.llm_configured

    def signing_key(self) -> str:
        """The JWT key. Required in production; generated once and kept in a
        git-ignored file in development so restarts keep sessions alive."""
        if self.JWT_SECRET_KEY:
            return self.JWT_SECRET_KEY
        if not self.DEBUG:
            raise RuntimeError("JWT_SECRET_KEY is not set.")
        if DEV_SECRET_FILE.exists():
            self.JWT_SECRET_KEY = DEV_SECRET_FILE.read_text().strip()
        else:
            self.JWT_SECRET_KEY = secrets.token_urlsafe(48)
            try:
                DEV_SECRET_FILE.write_text(self.JWT_SECRET_KEY)
                logger.warning(
                    f"Generated a development signing key at {DEV_SECRET_FILE.name}"
                )
            except OSError:
                # A read-only checkout (the container image, for one): the
                # key lives for this process only, and a restart signs
                # everyone out. Set JWT_SECRET_KEY to avoid that.
                logger.warning(
                    "Generated a development signing key in memory only; "
                    "set JWT_SECRET_KEY to keep sessions across restarts."
                )
        return self.JWT_SECRET_KEY

    def assert_production_ready(self) -> None:
        if self.DEBUG:
            return
        problems: List[str] = []
        if not self.JWT_SECRET_KEY:
            problems.append("JWT_SECRET_KEY is not set.")
        if not self.RATE_LIMITING:
            problems.append("RATE_LIMITING is off.")
        if _local(self.DATABASE_URL):
            problems.append("DATABASE_URL still points at localhost.")
        if self.REDIS_URL.startswith("memory://"):
            if self.REPLICAS > 1:
                problems.append("REDIS_URL=memory:// cannot serve more than one replica.")
        elif _local(self.REDIS_URL):
            problems.append("REDIS_URL still points at localhost.")
        if problems:
            raise RuntimeError("Not production ready: " + " ".join(problems))


settings = Settings()
