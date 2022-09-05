import secrets
from functools import lru_cache
from dotenv import find_dotenv
from pydantic import BaseSettings, EmailStr, PostgresDsn, validator, AnyHttpUrl
from typing import Any, Dict, Optional, List, Union


class Settings(BaseSettings):
    PROJECT_NAME: str = "Pastel Open API"
    PROJECT_DESCRIPTION: str = "Pastel Open API"

    API_V1_STR: str = "/api/v1"
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    SECRET_KEY: str = secrets.token_urlsafe(32)

    # BACKEND_CORS_ORIGINS is a JSON-formatted list of origins
    # e.g: '["http://localhost", "http://localhost:4200", "http://localhost:3000", \
    # "http://localhost:8080", "http://local.dockertoolbox.tiangolo.com"]'
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    PASTEL_RPC_USER: str
    PASTEL_RPC_PWD: str
    PASTEL_ID: str
    PASSPHRASE: str

    WN_BASE_URL: str = "http://127.0.0.1:8080"
    BASE_CASCADE_URL = f"{WN_BASE_URL}/openapi/cascade"
    BASE_SENSE_URL = f"{WN_BASE_URL}/openapi/sense"

    FILE_STORAGE: str

    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    SQLALCHEMY_DATABASE_URI: Optional[PostgresDsn] = None

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql",
            user=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_SERVER"),
            path=f"/{values.get('POSTGRES_DB') or ''}",
        )

    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    class Config:
        env_file = find_dotenv(usecwd=True)
        print("env_file is "+env_file)


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
