def _create(api, pid, **fields):
    res = api.post(f"/projects/{pid}/issues", {"title": "Fix login", **fields})
    assert res.status_code == 201, res.text
    return res.json()


def test_issue_numbers_are_sequential_per_project(project):
    owner, _, proj = project
    other = owner.post("/projects", {"key": "OPS", "name": "Ops"}).json()
    assert [_create(owner, proj["id"])["number"] for _ in range(3)] == [1, 2, 3]
    assert _create(owner, other["id"])["number"] == 1


def test_new_issues_go_to_the_end_of_their_column(project):
    owner, _, proj = project
    a = _create(owner, proj["id"])
    b = _create(owner, proj["id"])
    c = _create(owner, proj["id"], status="done")
    assert a["position"] < b["position"]
    assert c["position"] == a["position"]


def test_assignee_must_be_a_member(project, register):
    owner, member, proj = project
    outsider = register("out@example.com", "Out")
    res = owner.post(
        f"/projects/{proj['id']}/issues", {"title": "x", "assignee_id": outsider.user["id"]}
    )
    assert res.status_code == 422
    issue = _create(owner, proj["id"], assignee_id=member.user["id"])
    assert issue["assignee"]["name"] == "Member"


def test_list_filters(project):
    owner, member, proj = project
    pid = proj["id"]
    _create(owner, pid, title="Login broken", status="in_progress")
    _create(owner, pid, title="Signup copy", assignee_id=member.user["id"])
    _create(owner, pid, title="Login slow")
    assert owner.get(f"/projects/{pid}/issues").json()["total"] == 3
    assert owner.get(f"/projects/{pid}/issues", params={"q": "login"}).json()["total"] == 2
    assert (
        owner.get(f"/projects/{pid}/issues", params={"status": "in_progress"}).json()["total"] == 1
    )
    page = owner.get(f"/projects/{pid}/issues", params={"assignee_id": member.user["id"]}).json()
    assert [i["title"] for i in page["items"]] == ["Signup copy"]
    assert len(owner.get(f"/projects/{pid}/issues", params={"limit": 2}).json()["items"]) == 2


def test_update_bumps_version_and_logs_changes(project):
    owner, member, proj = project
    issue = _create(owner, proj["id"])
    res = member.patch(
        f"/issues/{issue['id']}",
        {"version": 1, "status": "in_review", "assignee_id": member.user["id"]},
    )
    assert res.status_code == 200, res.text
    updated = res.json()
    assert updated["version"] == 2 and updated["status"] == "in_review"

    activity = owner.get(f"/issues/{issue['id']}/activity").json()
    assert [a["kind"] for a in activity] == ["issue_created", "issue_updated"]
    assert activity[1]["data"]["changes"]["status"] == {"from": "todo", "to": "in_review"}
    assert activity[1]["actor"]["name"] == "Member"


def test_stale_version_is_rejected(project):
    owner, member, proj = project
    issue = _create(owner, proj["id"])
    assert owner.patch(f"/issues/{issue['id']}", {"version": 1, "title": "A"}).status_code == 200
    res = member.patch(f"/issues/{issue['id']}", {"version": 1, "title": "B"})
    assert res.status_code == 409
    assert owner.get(f"/issues/{issue['id']}").json()["title"] == "A"


def test_noop_update_keeps_version(project):
    owner, _, proj = project
    issue = _create(owner, proj["id"])
    res = owner.patch(f"/issues/{issue['id']}", {"version": 1, "title": "Fix login"})
    assert res.json()["version"] == 1


def test_unassign_and_null_checks(project):
    owner, member, proj = project
    issue = _create(owner, proj["id"], assignee_id=member.user["id"])
    res = owner.patch(f"/issues/{issue['id']}", {"version": 1, "assignee_id": None})
    assert res.status_code == 200 and res.json()["assignee"] is None
    assert owner.patch(f"/issues/{issue['id']}", {"version": 2, "title": None}).status_code == 422


def test_delete_permissions(project):
    owner, member, proj = project
    mine = _create(member, proj["id"])
    theirs = _create(owner, proj["id"])
    assert member.delete(f"/issues/{theirs['id']}").status_code == 403
    assert member.delete(f"/issues/{mine['id']}").status_code == 204
    assert owner.delete(f"/issues/{theirs['id']}").status_code == 204
    assert owner.get(f"/issues/{theirs['id']}").status_code == 404


def test_outsiders_cannot_touch_issues(project, register):
    owner, _, proj = project
    issue = _create(owner, proj["id"])
    outsider = register("out@example.com", "Out")
    assert outsider.get(f"/issues/{issue['id']}").status_code == 404
    assert outsider.patch(f"/issues/{issue['id']}", {"version": 1, "title": "x"}).status_code == 404
    assert outsider.post(f"/issues/{issue['id']}/comments", {"body": "hi"}).status_code == 404
