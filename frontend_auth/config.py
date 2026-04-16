import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    HOST: str = "127.0.0.1"
    PORT: int = 8810

    BACKEND_PUBLIC_URL: str = "https://voizely-backend.tailb8d083.ts.net"
    BACKEND_TIMEOUT: float = 10.0

    INTERNAL_API_KEY: str = ""

    LOG_DIR: str = "./logs"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()


AD_CONFIGS = [
    {
        "name": "Appworks",
        "server": os.getenv("AD_APPWORKS_SERVER", "172.20.0.101"),
        "domain_suffix": os.getenv("AD_APPWORKS_DOMAIN", "ais.local"),
        "email_suffix": os.getenv("AD_APPWORKS_EMAIL_SUFFIX", "appworks.co.th"),
        "base_dn": os.getenv("AD_APPWORKS_BASE", "DC=ais,DC=local"),
        "bind_user": os.getenv("AD_APPWORKS_BIND_USER", ""),
        "bind_password": os.getenv("AD_APPWORKS_BIND_PASSWORD", ""),
    },
    {
        "name": "iWired",
        "server": os.getenv("AD_IWIRED_SERVER", "192.168.0.14"),
        "domain_suffix": os.getenv("AD_IWIRED_DOMAIN", "iwired.co.th"),
        "email_suffix": os.getenv("AD_IWIRED_EMAIL_SUFFIX", "iwired.co.th"),
        "base_dn": os.getenv("AD_IWIRED_BASE", "DC=iwired,DC=co,DC=th"),
        "bind_user": os.getenv("AD_IWIRED_BIND_USER", ""),
        "bind_password": os.getenv("AD_IWIRED_BIND_PASSWORD", ""),
    },
]
