import io
import json
import pytest
from run import create_app
from app.repo import InMemoryRepo
from app.service import AnimeService

@pytest.fixture
def api_client():
    """Flask test client configured for API endpoint tests using InMemoryRepo."""
    app = create_app()
    app.testing = True
    repo = InMemoryRepo()
    svc = AnimeService(repo)
    app.config["SERVICE"] = svc
    with app.test_client() as client:
        yield client, svc

def test_api_create_and_list_animes(api_client):
    client, svc = api_client
    resp = client.post("/animes/new", data={"title": "ApiAnime", "total_episodes": "12"}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Anime created" in resp.data

    resp2 = client.get("/animes")
    assert resp2.status_code == 200
    assert b"ApiAnime" in resp2.data

def test_api_delete_requires_force_when_watched(api_client):
    client, svc = api_client
    u = svc.create_user("apiuser")
    a = svc.create_anime("ApiDelete", 3, None)
    svc.add_watch_entry(u.id, a.id, 1)
    resp = client.post(f"/animes/{a.id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert b"has watch entries" in resp.data

def test_api_export_json_and_status_code(api_client):
    client, svc = api_client
    u = svc.create_user("exp_user")
    a = svc.create_anime("ExpAnime", 5, None)
    svc.add_watch_entry(u.id, a.id, 5)
    resp = client.get(f"/users/{u.id}/watchlist/export?format=json")
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    data = json.loads(resp.data.decode())
    assert data and isinstance(data, list)
    assert any(d["anime_title"] == "ExpAnime" for d in data)

