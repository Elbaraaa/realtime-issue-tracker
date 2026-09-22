def test_create_and_list_projects(register):
    ada = register()
    res = ada.post("/projects", {"key": "API", "name": "Backend", "description": "Services"})
    assert res.status_code == 201
    assert [p["key"] for p in ada.get("/projects").json()] == ["API"]


def test_project_key_must_be_unique_and_well_formed(register):
    ada = register()
    assert ada.post("/projects", {"key": "API", "name": "One"}).status_code == 201
    assert ada.post("/projects", {"key": "API", "name": "Two"}).status_code == 409
    assert ada.post("/projects", {"key": "api", "name": "Lower"}).status_code == 422


def test_non_members_cannot_see_a_project(project, register):
    _, _, proj = project
    outsider = register("out@example.com", "Outsider")
    assert outsider.get(f"/projects/{proj['id']}").status_code == 404
    assert outsider.get(f"/projects/{proj['id']}/issues").status_code == 404
    assert outsider.get("/projects").json() == []


def test_members_listing_and_roles(project):
    owner, member, proj = project
    members = member.get(f"/projects/{proj['id']}/members").json()
    assert {(m["user"]["name"], m["role"]) for m in members} == {
        ("Owner", "owner"),
        ("Member", "member"),
    }


def test_only_owners_manage_members(project, register):
    owner, member, proj = project
    register("third@example.com", "Third")
    pid = proj["id"]
    assert (
        member.post(f"/projects/{pid}/members", {"email": "third@example.com"}).status_code == 403
    )
    assert owner.post(f"/projects/{pid}/members", {"email": "third@example.com"}).status_code == 201
    assert owner.post(f"/projects/{pid}/members", {"email": "third@example.com"}).status_code == 409
    assert owner.post(f"/projects/{pid}/members", {"email": "ghost@example.com"}).status_code == 404


def test_remove_member(project):
    owner, member, proj = project
    pid = proj["id"]
    assert owner.delete(f"/projects/{pid}/members/{owner.user['id']}").status_code == 400
    assert owner.delete(f"/projects/{pid}/members/{member.user['id']}").status_code == 204
    assert member.get(f"/projects/{pid}").status_code == 404
