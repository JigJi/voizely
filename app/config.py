from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    HOST: str = "127.0.0.1"
    PORT: int = 8800
    DATABASE_URL: str = "sqlite:///./speech_to_text.db"
    PG_DB: str = "speech_text"
    PG_USER: str = "postgres"
    PG_PASS: str = "P@ssw0rd"
    PG_HOST: str = "localhost"
    PG_PORT: int = 5432
    UPLOAD_DIR: str = "./uploads"

    @property
    def pg_url(self) -> str:
        from urllib.parse import quote_plus
        return f"postgresql://{self.PG_USER}:{quote_plus(self.PG_PASS)}@{self.PG_HOST}:{self.PG_PORT}/{self.PG_DB}"
    WHISPER_MODEL_SIZE: str = "Vinxscribe/biodatlab-whisper-th-large-v3-faster"
    WHISPER_DEVICE: str = "cuda"
    WHISPER_COMPUTE_TYPE: str = "float16"
    WHISPER_MODEL_DIR: str = "./models"
    OPEN_ROUNTER: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "scb10x/llama3.1-typhoon2-8b-instruct"
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    LLM_TIMEOUT: int = 300
    HF_TOKEN: str = ""
    GEMINI_API_KEY: str = ""
    DEEPGRAM_API_KEY: str = ""

    # Auth
    SECRET_KEY: str = "speech-text-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours
    AD_ENABLED: bool = False
    AD_SERVER: str = ""
    AD_DOMAIN: str = ""
    AD_BASE_DN: str = ""
    # Fixed user (when AD_ENABLED=False)
    FIXED_USERNAME: str = "admin"
    FIXED_PASSWORD: str = "admin"

    model_config = {"env_file": ".env"}

    @property
    def upload_path(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
