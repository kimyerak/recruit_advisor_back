from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str = ""
    model_name: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    vectorstore_path: str = "backend/knowledge/vectorstore"
    chunk_size: int = 800
    chunk_overlap: int = 100

    class Config:
        env_file = ".env"

settings = Settings()
