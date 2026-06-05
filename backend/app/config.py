from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
    )

    openai_api_key: str = ""
    openai_review_model: str = "gpt-4o-mini"
    openai_vision_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"
    database_url: str = "sqlite:///./northwind.db"
    chroma_path: str = "./chroma_data"
    upload_dir: str = "./uploads"
    policies_dir: str = "../data/policies"
    submissions_seed_dir: str = "../data/submissions"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    min_retrieval_score: float = 0.28
    top_k_policies: int = 8

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def resolve_path(self, p: str) -> Path:
        path = Path(p)
        if path.is_absolute():
            return path
        return (self.project_root / "backend" / p).resolve()


settings = Settings()
