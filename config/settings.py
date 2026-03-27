from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)  # os.environ에도 설정 (LangChain이 직접 읽음)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_PATH), extra="ignore")

    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    emb_model_name: str = "text-embedding-3-small"
    vectorstore_path: str = "backend/knowledge/vectorstore"
    chunk_size: int = 800
    chunk_overlap: int = 100

settings = Settings()
