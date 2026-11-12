"""Central configuration read from environment variables (or a local `.env`).

pydantic-settings validates every value at start-up, so a missing or malformed setting
fails fast instead of in the middle of a request.

Some variables were renamed when the code moved to English. The old Spanish names are still
accepted as aliases (`AliasChoices`) so an existing deployment keeps working until its
environment is updated; see docs/deployment.md for the full table.
"""
from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _env(name: str, *legacy: str) -> AliasChoices:
    return AliasChoices(name, *legacy)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore",
                                      populate_by_name=True)

    APP_NAME: str = "Predictor de Brotes Nariño"  # shown in the OpenAPI docs (Spanish UI)
    ENV: str = "development"  # development | production
    API_PREFIX: str = "/api/v1"

    # Database: PostgreSQL (Neon) in production; SQLite is enough for local development.
    DATABASE_URL: str = "sqlite:///./dev.db"

    # Security
    JWT_SECRET: str = "change-me-in-production-with-a-long-random-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    CRON_SECRET: str = "change-me-cron-secret"

    # CORS: comma-separated origins plus an optional regex (e.g. Vercel preview URLs)
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    CORS_ORIGIN_REGEX: str | None = None

    # Initial administrator created by the seed
    ADMIN_EMAIL: str = "admin@predictor.co"
    ADMIN_PASSWORD: str = "Admin2026*"
    ADMIN_NAME: str = Field("Administrador", validation_alias=_env("ADMIN_NAME", "ADMIN_NOMBRE"))
    # Demo users (PHARMACY and CITIZEN) used in presentations
    DEMO_PASSWORD: str = "Demo2026*"

    # Open-Meteo (free, no API key)
    OPEN_METEO_FORECAST_URL: str = "https://api.open-meteo.com/v1/forecast"
    OPEN_METEO_ARCHIVE_URL: str = "https://archive-api.open-meteo.com/v1/archive"
    HTTP_TIMEOUT_SECONDS: float = Field(20.0, validation_alias=_env("HTTP_TIMEOUT_SECONDS", "HTTP_TIMEOUT_SEGUNDOS"))
    # When true the seed downloads the REAL historical weather and only simulates it if that fails
    SEED_REAL_WEATHER: bool = Field(True, validation_alias=_env("SEED_REAL_WEATHER", "SEED_CLIMA_REAL"))
    SEED_START_YEAR: int = Field(2020, validation_alias=_env("SEED_START_YEAR", "SEED_ANIO_INICIO"))

    # SIVIGILA / INS published on datos.gov.co (Socrata API): weekly cases per event and municipality.
    SOCRATA_URL: str = "https://www.datos.gov.co/resource/4hyg-wa9d.json"
    SOCRATA_APP_TOKEN: str | None = None  # optional: raises the request quota
    SIVIGILA_DEPARTMENT: str = Field("52", validation_alias=_env("SIVIGILA_DEPARTMENT", "SIVIGILA_DEPARTAMENTO"))

    # Train in the background on start-up when there is no active model (the engine does it)
    TRAIN_ON_STARTUP: bool = Field(True, validation_alias=_env("TRAIN_ON_STARTUP", "ENTRENAR_AL_INICIO"))

    # Token the three services use to authenticate each other inside the container (gRPC metadata
    # and the realtime hub's internal endpoint). Defence in depth: they only listen on 127.0.0.1.
    INTERNAL_TOKEN: str = Field("internal-token-change-me",
                                validation_alias=_env("INTERNAL_TOKEN", "ENGINE_GRPC_TOKEN", "MOTOR_GRPC_TOKEN"))

    # Prediction engine (gRPC). It only listens on 127.0.0.1 inside the container; the gateway and
    # the realtime hub are its clients.
    ENGINE_GRPC_ADDRESS: str = Field("127.0.0.1:50051",
                                     validation_alias=_env("ENGINE_GRPC_ADDRESS", "MOTOR_GRPC_DIRECCION"))
    ENGINE_GRPC_TIMEOUT_S: float = Field(15.0, validation_alias=_env("ENGINE_GRPC_TIMEOUT_S", "MOTOR_GRPC_TIMEOUT_S"))
    ENGINE_GRPC_THREADS: int = Field(32, validation_alias=_env("ENGINE_GRPC_THREADS", "MOTOR_GRPC_HILOS"))
    # How often the engine checks whether the active alerts changed
    ENGINE_ALERT_POLL_S: float = Field(10.0, validation_alias=_env("ENGINE_ALERT_POLL_S", "MOTOR_INTERVALO_ALERTAS_S"))
    # The in-memory dataset is rebuilt at least every 15 minutes
    ENGINE_CACHE_TTL_S: float = Field(900.0, validation_alias=_env("ENGINE_CACHE_TTL_S", "MOTOR_CACHE_TTL_S"))

    # Realtime hub (WebSocket). The gateway publishes system events to it over loopback HTTP.
    REALTIME_INTERNAL_URL: str = "http://127.0.0.1:8002"
    REALTIME_MAX_CONNECTIONS: int = 200
    REALTIME_HEARTBEAT_S: float = 25.0

    # Keep-awake for free hosting plans that sleep without inbound traffic: the realtime service
    # requests its own public URL (Render exposes it as RENDER_EXTERNAL_URL). Off when no URL is known.
    KEEP_AWAKE: bool = True
    KEEP_AWAKE_URL: str | None = Field(None, validation_alias=_env("KEEP_AWAKE_URL", "RENDER_EXTERNAL_URL"))
    KEEP_AWAKE_INTERVAL_S: float = 600.0  # must stay under the platform's idle limit (15 min on Render)
    KEEP_AWAKE_HOURS: str = "0-24"  # local hours "start-end"; e.g. "6-23" lets the service sleep at night
    LOCAL_UTC_OFFSET_HOURS: int = -5  # Colombia (no daylight saving time)

    # Google Trends (pytrends is unofficial and may be blocked; there is a DB cache and CSV fallback)
    TRENDS_ENABLED: bool = Field(True, validation_alias=_env("TRENDS_ENABLED", "TRENDS_HABILITADO"))
    TRENDS_REGION: str = "CO-NAR"
    TRENDS_CSV_DIR: str = "data/trends"
    TRENDS_PAUSE_SECONDS: float = Field(2.0, validation_alias=_env("TRENDS_PAUSE_SECONDS", "TRENDS_PAUSA_SEGUNDOS"))

    # E-mail alerts through Resend (optional; free plan: 100 e-mails/day). Nothing is sent without a key.
    RESEND_API_KEY: str | None = None
    RESEND_URL: str = "https://api.resend.com/emails"
    ALERT_EMAIL_SENDER: str = Field("Predictor de Brotes <onboarding@resend.dev>",
                                    validation_alias=_env("ALERT_EMAIL_SENDER", "ALERTAS_EMAIL_REMITENTE"))
    # Comma-separated recipients of every alert (health department, administrators)
    ALERT_EMAIL_RECIPIENTS: str = Field("", validation_alias=_env("ALERT_EMAIL_RECIPIENTS", "ALERTAS_EMAIL_DESTINO"))
    # Also e-mail registered citizens the alerts of THEIR municipality (one e-mail per person)
    ALERTS_TO_CITIZENS: bool = Field(True, validation_alias=_env("ALERTS_TO_CITIZENS", "ALERTAS_A_CIUDADANOS"))
    FRONTEND_URL: str = "http://localhost:3000"
    # Secret shared with Vercel for on-demand revalidation of the ISR pages (optional)
    REVALIDATE_SECRET: str | None = Field(None, validation_alias=_env("REVALIDATE_SECRET", "REVALIDAR_SECRET"))

    @field_validator("DATABASE_URL")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        # Neon/Render hand out "postgres://" or "postgresql://"; SQLAlchemy 2 + psycopg3 needs the
        # explicit "postgresql+psycopg://" dialect.
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def alert_recipients(self) -> list[str]:
        return [c.strip() for c in self.ALERT_EMAIL_RECIPIENTS.split(",") if c.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
