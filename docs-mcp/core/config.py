from functools import lru_cache
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        extra='ignore',
        populate_by_name=True,
    )
    collection_name: str = Field(
        default='docs_chunks',
        validation_alias=AliasChoices('collection_name', 'DOCS_MCP_COLLECTION'),
    )
    qdrant_url: str = Field(
        default='http://localhost:6333',
        validation_alias=AliasChoices('qdrant_url', 'QDRANT_URL'),
    )
    redis_url: str = Field(
        default='redis://localhost:6379/0',
        validation_alias=AliasChoices('redis_url', 'REDIS_URL'),
    )
    embedding_model: str = Field(
        default='BAAI/bge-large-en-v1.5',
        validation_alias=AliasChoices('embedding_model', 'EMBEDDING_MODEL'),
    )
    lightweight_embedding_model: str = Field(
        default='nomic-ai/nomic-embed-text-v1.5',
        validation_alias=AliasChoices('lightweight_embedding_model', 'LIGHTWEIGHT_EMBEDDINGS_MODEL'),
    )
    reranker_model: str = Field(
        default='BAAI/bge-reranker-large',
        validation_alias=AliasChoices('reranker_model', 'RERANKER_MODEL'),
    )
    embedding_dim: int = Field(
        default=1024,
        validation_alias=AliasChoices('embedding_dim', 'EMBEDDING_DIM'),
    )
    use_lightweight_embeddings: bool = Field(
        default=False,
        validation_alias=AliasChoices('use_lightweight_embeddings', 'USE_LIGHTWEIGHT_EMBEDDINGS'),
    )
    local_data_dir: str = Field(
        default='./data',
        validation_alias=AliasChoices('local_data_dir', 'LOCAL_DATA_DIR'),
    )
    chunk_min_tokens: int = Field(
        default=500,
        validation_alias=AliasChoices('chunk_min_tokens', 'CHUNK_MIN_TOKENS'),
    )
    chunk_max_tokens: int = Field(
        default=1200,
        validation_alias=AliasChoices('chunk_max_tokens', 'CHUNK_MAX_TOKENS'),
    )
    chunk_overlap_tokens: int = Field(
        default=125,
        validation_alias=AliasChoices('chunk_overlap_tokens', 'CHUNK_OVERLAP_TOKENS'),
    )
    batch_size: int = Field(
        default=16,
        validation_alias=AliasChoices('batch_size', 'BATCH_SIZE'),
    )
    query_cache_ttl_seconds: int = Field(
        default=300,
        validation_alias=AliasChoices('query_cache_ttl_seconds', 'QUERY_CACHE_TTL_SECONDS'),
    )
    ingest_batch_chunks: int = Field(
        default=64,
        validation_alias=AliasChoices('ingest_batch_chunks', 'INGEST_BATCH_CHUNKS'),
    )
    retrieve_candidate_multiplier: int = Field(
        default=3,
        validation_alias=AliasChoices('retrieve_candidate_multiplier', 'RETRIEVE_CANDIDATE_MULTIPLIER'),
    )
    max_retrieval_candidates: int = Field(
        default=40,
        validation_alias=AliasChoices('max_retrieval_candidates', 'MAX_RETRIEVAL_CANDIDATES'),
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()
