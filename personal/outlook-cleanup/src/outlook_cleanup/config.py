from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from platformdirs import user_config_dir
from pydantic import BaseModel, Field


class Config(BaseModel):
    tenant_id: str = "common"
    client_id: str
    purge_folder_name: str = "Permanently Delete"
    anthropic_api_key: str | None = None
    model: str = "claude-sonnet-4-6"
    max_messages: int = 200
    preferences: str = (
        "You are triaging the user's Outlook inbox. They consider an email "
        "UNWANTED when it is irrelevant marketing, mass unsolicited mail, "
        "off-topic for their work, or the kind of message they routinely delete "
        "without reading. Newsletters they never asked for, sales promotions, "
        "vendor cold outreach, and notification spam are all UNWANTED. "
        "Anything from a human colleague, anything that looks like a real "
        "conversation, security alerts for their own accounts, receipts, "
        "calendar invites, and bills are KEEP."
    )


def config_dir() -> Path:
    p = Path(user_config_dir("outlook-cleanup"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_path() -> Path:
    return config_dir() / "config.yaml"


def rules_path() -> Path:
    return config_dir() / "rules.yaml"


def runs_dir() -> Path:
    p = config_dir() / "runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def token_cache_path() -> Path:
    return config_dir() / "token_cache.bin"


@lru_cache(maxsize=1)
def load_config() -> Config:
    path = config_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Config not found at {path}. Copy config.example.yaml there and fill it in."
        )
    data = yaml.safe_load(path.read_text()) or {}
    if "anthropic_api_key" not in data or not data["anthropic_api_key"]:
        data["anthropic_api_key"] = os.environ.get("ANTHROPIC_API_KEY")
    return Config(**data)
