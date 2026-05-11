import httpx
import respx

from outlook_cleanup.graph import GRAPH_BASE, GraphClient


@respx.mock
def test_list_folders_pages():
    page1 = {
        "value": [
            {"displayName": "Inbox", "id": "inbox-id"},
            {"displayName": "Permanently Delete", "id": "purge-id"},
        ],
        "@odata.nextLink": f"{GRAPH_BASE}/me/mailFolders?page=2",
    }
    page2 = {
        "value": [{"displayName": "Archive", "id": "archive-id"}],
    }
    respx.get(f"{GRAPH_BASE}/me/mailFolders?$top=100").mock(
        return_value=httpx.Response(200, json=page1)
    )
    respx.get(f"{GRAPH_BASE}/me/mailFolders?page=2").mock(
        return_value=httpx.Response(200, json=page2)
    )

    with GraphClient("tok") as gc:
        folders = gc.list_folders()
    assert folders == {
        "Inbox": "inbox-id",
        "Permanently Delete": "purge-id",
        "Archive": "archive-id",
    }


@respx.mock
def test_find_folder_id_missing_raises():
    respx.get(f"{GRAPH_BASE}/me/mailFolders?$top=100").mock(
        return_value=httpx.Response(200, json={"value": [{"displayName": "Inbox", "id": "i"}]})
    )
    with GraphClient("tok") as gc:
        try:
            gc.find_folder_id("Permanently Delete")
        except KeyError as e:
            assert "Permanently Delete" in str(e)
        else:
            raise AssertionError("expected KeyError")


@respx.mock
def test_move_message_sends_destination_id():
    route = respx.post(f"{GRAPH_BASE}/me/messages/m-1/move").mock(
        return_value=httpx.Response(201, json={"id": "new-id"})
    )
    with GraphClient("tok") as gc:
        new_id = gc.move_message("m-1", "purge-id")
    assert new_id == "new-id"
    assert route.called
    body = route.calls.last.request.read()
    assert b'"destinationId":"purge-id"' in body.replace(b" ", b"")


@respx.mock
def test_list_inbox_paginates_and_respects_limit():
    page1 = {
        "value": [
            {
                "id": f"m-{i}",
                "subject": f"s{i}",
                "from": {"emailAddress": {"name": "A", "address": f"a{i}@x.com"}},
                "bodyPreview": "",
                "receivedDateTime": "2026-05-11T12:00:00Z",
                "isRead": False,
                "inferenceClassification": "focused",
                "hasAttachments": False,
            }
            for i in range(3)
        ],
        "@odata.nextLink": f"{GRAPH_BASE}/me/mailFolders/inbox/messages?page=2",
    }
    respx.get(url__startswith=f"{GRAPH_BASE}/me/mailFolders/inbox/messages?$select=").mock(
        return_value=httpx.Response(200, json=page1)
    )

    with GraphClient("tok") as gc:
        msgs = list(gc.list_inbox_messages(limit=2))
    assert len(msgs) == 2
    assert msgs[0].sender.address == "a0@x.com"
