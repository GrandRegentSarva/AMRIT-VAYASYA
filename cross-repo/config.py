from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore', populate_by_name=True)

    qdrant_url: str = Field(
        default='http://localhost:6333',
        validation_alias=AliasChoices('qdrant_url', 'QDRANT_URL'),
    )
    collection_name: str = Field(
        default='docs_chunks',
        validation_alias=AliasChoices('collection_name', 'COLLECTION_NAME'),
    )
    neo4j_uri: str = Field(
        default='bolt://localhost:7687',
        validation_alias=AliasChoices('neo4j_uri', 'NEO4J_URI'),
    )
    neo4j_user: str = Field(
        default='neo4j',
        validation_alias=AliasChoices('neo4j_user', 'NEO4J_USER'),
    )
    neo4j_password: str = Field(
        default='vayasya_dev',
        validation_alias=AliasChoices('neo4j_password', 'NEO4J_PASSWORD'),
    )
    graph_data_dir: str = Field(
        default='./data',
        validation_alias=AliasChoices('graph_data_dir', 'GRAPH_DATA_DIR'),
    )
    cross_repo_port: int = Field(
        default=8001,
        validation_alias=AliasChoices('cross_repo_port', 'CROSS_REPO_PORT'),
    )
    groq_api_key: str = Field(
        default='',
        validation_alias=AliasChoices('groq_api_key', 'GROQ_API_KEY'),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
