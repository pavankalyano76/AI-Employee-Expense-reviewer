from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    pinecone_api_key: str
    pinecone_index_name: str = "northwind-policies"

    database_url: str = "sqlite:///./storage/northwind.db"
    upload_dir: Path = Path("storage/uploads")
    policies_dir: Path = Path("data/policies")
    submissions_dir: Path = Path("data/submissions")

    class Config:
        env_file = ".env"


settings = Settings()
