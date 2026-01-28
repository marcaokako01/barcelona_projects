# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # --- Configurações Gerais ---
    PROJECT_NAME: str = "Barcelona Partners AI"
    API_V1_STR: str = "/api/v1"  # <--- ESTA FOI A LINHA QUE FALTOU
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # --- Chaves de API ---
    OPENAI_API_KEY: str
    VAPI_API_KEY: str
    
    # --- Banco de Dados Vetorial ---
    PINECONE_API_KEY: str
    PINECONE_ENV: str = "us-east-1"

    # --- Banco de Dados de Leads ---
    AZURE_STORAGE_CONNECTION_STRING: str = "UseDevelopmentStorage=true"

    # --- Negócio ---
    DEFAULT_CLOSER_NAME: str = "Fernanda Aro"

    # --- Configuração do Pydantic ---
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Cria a instância final
settings = Settings()