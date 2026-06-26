from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    debug: bool = False
    secret_key: str

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # Kryptering (Fernet key til bruger-API-nøgler)
    encryption_key: str

    # AI providers — systemets egne nøgler
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    ollama_base_url: str | None = None

    # Standardmodeller — kan overrides via env vars
    # Ændres kun her (ikke i agent_registry eller Python-kode)
    anthropic_default_model: str = "claude-sonnet-4-6"
    openai_default_model: str = "gpt-4o"

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""
    stripe_price_professional: str = ""
    stripe_price_enterprise: str = ""

    # Frontend URL (til Stripe redirect)
    frontend_url: str = "http://localhost:3000"

    # Redis — valgfri; in-memory fallback bruges hvis ikke sat
    redis_url: str | None = None

    # Sentry
    sentry_dsn: str | None = None

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]
    # Regex for dynamiske origins — dækker alle Vercel preview-deployments automatisk
    cors_allow_origin_regex: str = r"https?://(.*\.vercel\.app|localhost(:\d+)?)"

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)


settings = Settings()  # type: ignore[call-arg]
