from __future__ import annotations

import time
from datetime import datetime
from typing import Iterator

import httpx

from outlook_cleanup.models import Message

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

MESSAGE_SELECT = ",".join([
    "id",
    "subject",
    "from",
    "sender",
    "bodyPreview",
    "receivedDateTime",
    "isRead",
    "inferenceClassification",
    "hasAttachments",
])


class GraphClient:
    def __init__(self, access_token: str, *, timeout: float = 30.0):
        self._client = httpx.Client(
            base_url=GRAPH_BASE,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GraphClient":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        for attempt in range(5):
            r = self._client.request(method, url, **kwargs)
            if r.status_code == 429 or 500 <= r.status_code < 600:
                retry_after = int(r.headers.get("Retry-After", 0) or 0)
                delay = retry_after if retry_after > 0 else 2 ** attempt
                time.sleep(min(delay, 30))
                continue
            r.raise_for_status()
            return r
        r.raise_for_status()
        return r

    def list_folders(self) -> dict[str, str]:
        """Return {displayName: id} for all top-level mail folders."""
        folders: dict[str, str] = {}
        url = "/me/mailFolders?$top=100"
        while url:
            r = self._request("GET", url)
            data = r.json()
            for f in data.get("value", []):
                folders[f["displayName"]] = f["id"]
            url = data.get("@odata.nextLink", "").replace(GRAPH_BASE, "") or None
        return folders

    def find_folder_id(self, display_name: str) -> str:
        folders = self.list_folders()
        if display_name not in folders:
            available = ", ".join(sorted(folders)) or "(none)"
            raise KeyError(
                f"Folder {display_name!r} not found. Available top-level folders: {available}"
            )
        return folders[display_name]

    def list_inbox_messages(
        self,
        *,
        limit: int = 200,
        since: datetime | None = None,
    ) -> Iterator[Message]:
        params = [
            f"$select={MESSAGE_SELECT}",
            "$top=50",
            "$orderby=receivedDateTime desc",
        ]
        if since is not None:
            params.append(f"$filter=receivedDateTime ge {since.isoformat()}")
        url = "/me/mailFolders/inbox/messages?" + "&".join(params)
        yielded = 0
        while url and yielded < limit:
            r = self._request("GET", url)
            data = r.json()
            for raw in data.get("value", []):
                yield Message.from_graph(raw)
                yielded += 1
                if yielded >= limit:
                    return
            url = data.get("@odata.nextLink", "").replace(GRAPH_BASE, "") or None

    def move_message(self, message_id: str, destination_id: str) -> str:
        r = self._request(
            "POST",
            f"/me/messages/{message_id}/move",
            json={"destinationId": destination_id},
        )
        return r.json().get("id", "")
