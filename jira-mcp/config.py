from __future__ import annotations

import os

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore', populate_by_name=True)

    cross_repo_url: str = Field(
        default='http://localhost:8001',
        validation_alias=AliasChoices('cross_repo_url', 'CROSS_REPO_URL'),
    )
    jira_server: str = Field(
        default='',
        validation_alias=AliasChoices('jira_server', 'JIRA_SERVER'),
    )
    jira_email: str = Field(
        default='',
        validation_alias=AliasChoices('jira_email', 'JIRA_EMAIL'),
    )
    jira_api_token: str = Field(
        default='',
        validation_alias=AliasChoices('jira_api_token', 'JIRA_API_TOKEN'),
    )
    jira_mcp_port: int = Field(
        default=8002,
        validation_alias=AliasChoices('jira_mcp_port', 'JIRA_MCP_PORT'),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
