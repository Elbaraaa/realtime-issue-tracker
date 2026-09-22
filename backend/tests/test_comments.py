def test_comments_are_listed_in_order_and_logged(project):
    owner, member, proj = project
    issue = owner.post(f"/projects/{proj['id']}/issues", {"title": "Bug"}).json()
    iid = issue["id"]
    assert owner.post(f"/issues/{iid}/comments", {"body": "Can repro"}).status_code == 201
    assert member.post(f"/issues/{iid}/comments", {"body": "On it"}).status_code == 201
    comments = owner.get(f"/issues/{iid}/comments").json()
    assert [(c["author"]["name"], c["body"]) for c in comments] == [
        ("Owner", "Can repro"),
        ("Member", "On it"),
    ]
    kinds = [a["kind"] for a in owner.get(f"/issues/{iid}/activity").json()]
    assert kinds == ["issue_created", "comment_added", "comment_added"]


def test_empty_comment_rejected(project):
    owner, _, proj = project
    issue = owner.post(f"/projects/{proj['id']}/issues", {"title": "Bug"}).json()
    assert owner.post(f"/issues/{issue['id']}/comments", {"body": ""}).status_code == 422
