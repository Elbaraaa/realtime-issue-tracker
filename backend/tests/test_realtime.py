import pytest
from starlette.websockets import WebSocketDisconnect


def _connect(client, pid):
    return client.websocket_connect(f"/api/ws/projects/{pid}")


def test_members_receive_project_events(client, project):
    owner, member, proj = project
    with _connect(client, proj["id"]) as ws:
        ws.send_json({"token": member.token})
        assert ws.receive_json() == {"type": "ready"}

        issue = owner.post(f"/projects/{proj['id']}/issues", {"title": "Live"}).json()
        event = ws.receive_json()
        assert event["type"] == "activity"
        assert event["kind"] == "issue_created"
        assert event["issue_id"] == issue["id"]
        assert event["actor_id"] == owner.user["id"]

        owner.patch(f"/issues/{issue['id']}", {"version": 1, "status": "done"})
        assert ws.receive_json()["data"]["changes"]["status"]["to"] == "done"


def test_bad_token_is_closed(client, project):
    _, _, proj = project
    with _connect(client, proj["id"]) as ws:
        ws.send_json({"token": "nope"})
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == 4401


def test_non_member_is_closed(client, project, register):
    _, _, proj = project
    outsider = register("out@example.com", "Out")
    with _connect(client, proj["id"]) as ws:
        ws.send_json({"token": outsider.token})
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == 4403


def test_events_are_scoped_to_their_project(client, project):
    owner, _, proj = project
    other = owner.post("/projects", {"key": "OPS", "name": "Ops"}).json()
    with _connect(client, proj["id"]) as ws:
        ws.send_json({"token": owner.token})
        ws.receive_json()
        owner.post(f"/projects/{other['id']}/issues", {"title": "Elsewhere"})
        owner.post(f"/projects/{proj['id']}/issues", {"title": "Here"})
        assert ws.receive_json()["data"]["title"] == "Here"
