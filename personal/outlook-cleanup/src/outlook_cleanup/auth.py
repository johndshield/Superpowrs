from __future__ import annotations

import sys
from pathlib import Path

import msal

from outlook_cleanup.config import Config, token_cache_path

SCOPES = ["Mail.ReadWrite"]
AUTHORITY_TMPL = "https://login.microsoftonline.com/{tenant_id}"


def _load_cache(path: Path) -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    if path.exists():
        cache.deserialize(path.read_text())
    return cache


def _save_cache(path: Path, cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        path.write_text(cache.serialize())


def _build_app(config: Config, cache: msal.SerializableTokenCache) -> msal.PublicClientApplication:
    return msal.PublicClientApplication(
        client_id=config.client_id,
        authority=AUTHORITY_TMPL.format(tenant_id=config.tenant_id),
        token_cache=cache,
    )


def get_token(config: Config, interactive: bool = False) -> str:
    """Return an access token, refreshing silently or prompting if needed."""
    cache_path = token_cache_path()
    cache = _load_cache(cache_path)
    app = _build_app(config, cache)

    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not result:
        if not interactive:
            raise RuntimeError(
                "No cached token and not interactive. Run `outlook-cleanup auth login` first."
            )
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Failed to start device flow: {flow}")
        print(flow["message"], file=sys.stderr, flush=True)
        result = app.acquire_token_by_device_flow(flow)

    _save_cache(cache_path, cache)

    if "access_token" not in result:
        raise RuntimeError(f"Auth failed: {result.get('error_description') or result}")
    return result["access_token"]


def login(config: Config) -> None:
    get_token(config, interactive=True)
