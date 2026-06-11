from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://foundry:foundry_password@localhost:5432/foundry"
    
    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "foundry_neo4j"
    
    # LanceDB
    LANCEDB_URI: str = "./data/lancedb"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # Security
    JWT_SECRET: str = "supersecret_hackathon_key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 2880 # 48 hours
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
