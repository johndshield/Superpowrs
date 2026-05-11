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

    def list_folders(self, *, recursive: bool = True) -> dict[str, str]:
        """Return {path: id} for mail folders.

        If recursive=True, walks the full folder tree and uses paths like
        "Inbox/Permanently Delete" as keys. Otherwise only top-level
        displayNames.
        """
        folders: dict[str, str] = {}

        def walk(url: str, prefix: str) -> None:
            while url:
                r = self._request("GET", url)
                data = r.json()
                for f in data.get("value", []):
                    name = f["displayName"]
                    path = f"{prefix}/{name}" if prefix else name
                    folders[path] = f["id"]
                    if recursive and f.get("childFolderCount", 0) > 0:
                        walk(f"/me/mailFolders/{f['id']}/childFolders?$top=100", path)
                url = data.get("@odata.nextLink", "").replace(GRAPH_BASE, "") or None

        walk("/me/mailFolders?$top=100", "")
        return folders

    def find_folder_id(self, display_name: str) -> str:
        folders = self.list_folders()
        # Exact path match first
        if display_name in folders:
            return folders[display_name]
        # Fall back to leaf-name match (folder name anywhere in tree)
        leaf_matches = {p: i for p, i in folders.items() if p.rsplit("/", 1)[-1] == display_name}
        if len(leaf_matches) == 1:
            return next(iter(leaf_matches.values()))
        if len(leaf_matches) > 1:
            paths = ", ".join(sorted(leaf_matches))
            raise KeyError(
                f"Folder name {display_name!r} is ambiguous. Use a full path. Matches: {paths}"
            )
        available = ", ".join(sorted(folders)) or "(none)"
        raise KeyError(
            f"Folder {display_name!r} not found. Available folders: {available}"
        )

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
