"""
Central place for all settings.
Values are read from environment variables (or a `.env` file) so you never
hard-code secrets like database passwords into the source code.
"""
from pydantic_settings import BaseSettings
from pathlib import Path

# Folder that contains this file -> backend/app -> backend
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # --- Postgres connection ---
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "vendor_intelligence"

    # --- ML model files ---
    models_dir: Path = BASE_DIR / "models"
    scaler_path: Path = BASE_DIR / "models" / "scaler.pkl"
    flag_model_path: Path = BASE_DIR / "models" / "predict_flag_invoice.pkl"
    freight_model_path: Path = BASE_DIR / "models" / "predict_freight_model.pkl"

    # --- GenAI (Gemini via LangChain) ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    # --- CORS: which frontend origins may call this API ---
    allowed_origins: list[str] = [
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    @property
    def database_url(self) -> str:
        from urllib.parse import quote_plus
        encoded_password = quote_plus(self.postgres_password)
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{encoded_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
