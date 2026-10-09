"""Configuración central leída de variables de entorno (.env).

Decisión: pydantic-settings valida tipos al arrancar; si falta una variable
crítica la app falla de inmediato en lugar de fallar en medio de una petición.
"""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Predictor de Brotes Nariño"
    ENV: str = "development"  # development | production
    API_PREFIX: str = "/api/v1"

    # Base de datos: PostgreSQL (Neon/Supabase) en producción; SQLite sirve para desarrollo rápido.
    DATABASE_URL: str = "sqlite:///./dev.db"

    # Seguridad
    JWT_SECRET: str = "cambia-esto-en-produccion-por-un-secreto-largo"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    CRON_SECRET: str = "cambia-este-secreto-del-cron"

    # CORS: lista separada por comas + regex opcional (p. ej. previews de Vercel)
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    CORS_ORIGIN_REGEX: str | None = None

    # Usuario administrador inicial que crea el seed
    ADMIN_EMAIL: str = "admin@predictor.co"
    ADMIN_PASSWORD: str = "Admin2026*"
    ADMIN_NOMBRE: str = "Administrador"
    # Usuarios demo (FARMACIA y CIUDADANO) para la presentación
    DEMO_PASSWORD: str = "Demo2026*"

    # Open-Meteo (gratis, sin API key)
    OPEN_METEO_FORECAST_URL: str = "https://api.open-meteo.com/v1/forecast"
    OPEN_METEO_ARCHIVE_URL: str = "https://archive-api.open-meteo.com/v1/archive"
    HTTP_TIMEOUT_SEGUNDOS: float = 20.0
    # Si es true, el seed intenta descargar el clima histórico REAL de Open-Meteo
    # y solo si falla usa clima simulado.
    SEED_CLIMA_REAL: bool = True
    SEED_ANIO_INICIO: int = 2020

    # SIVIGILA / INS publicado en datos.gov.co (API Socrata). Dataset "Datos de Vigilancia en
    # Salud Pública de Colombia": casos por evento, municipio de ocurrencia y semana (2007-2022).
    SOCRATA_URL: str = "https://www.datos.gov.co/resource/4hyg-wa9d.json"
    SOCRATA_APP_TOKEN: str | None = None  # opcional: sube el límite de peticiones
    SIVIGILA_DEPARTAMENTO: str = "52"  # Nariño

    # Modelo predictivo: si no hay modelos entrenados, entrenarlos en segundo plano al arrancar
    ENTRENAR_AL_INICIO: bool = True

    # Google Trends (pytrends no es oficial: puede fallar o bloquearse; hay caché en BD y CSV de respaldo)
    TRENDS_HABILITADO: bool = True
    TRENDS_REGION: str = "CO-NAR"
    TRENDS_CSV_DIR: str = "data/trends"
    TRENDS_PAUSA_SEGUNDOS: float = 2.0

    # Alertas por correo con Resend (opcional; plan gratis: 100 correos/día). Sin API key no se envía nada.
    RESEND_API_KEY: str | None = None
    RESEND_URL: str = "https://api.resend.com/emails"
    ALERTAS_EMAIL_REMITENTE: str = "Predictor de Brotes <onboarding@resend.dev>"
    ALERTAS_EMAIL_DESTINO: str = ""  # correos separados por coma (secretaría de salud, administradores)
    # Enviar también a los ciudadanos registrados las alertas de SU municipio (un correo por persona)
    ALERTAS_A_CIUDADANOS: bool = True
    FRONTEND_URL: str = "http://localhost:5173"

    @field_validator("DATABASE_URL")
    @classmethod
    def normalizar_url(cls, v: str) -> str:
        # Neon/Render/Supabase entregan "postgres://" o "postgresql://"; SQLAlchemy 2 + psycopg3
        # necesita el dialecto explícito "postgresql+psycopg://".
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def destinatarios_alertas(self) -> list[str]:
        return [c.strip() for c in self.ALERTAS_EMAIL_DESTINO.split(",") if c.strip()]

    @property
    def es_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
