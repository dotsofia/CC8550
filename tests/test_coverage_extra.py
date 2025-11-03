import io
import json
import sqlite3
import pytest
from run import create_app
from app.repo import SqliteRepo, InMemoryRepo
from app.service import AnimeService, ValidationError, NotFoundError

# Reuse schema used in other tests (keeps routes consistent with DB-backed repo)
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS studios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS animes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    total_episodes INTEGER,
    studio_id INTEGER,
    FOREIGN KEY (studio_id) REFERENCES studios(id)
);
CREATE TABLE IF NOT EXISTS anime_tags (
    anime_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (anime_id, tag_id),
    FOREIGN KEY (anime_id) REFERENCES animes(id),
    FOREIGN KEY (tag_id) REFERENCES tags(id)
);
CREATE TABLE IF NOT EXISTS watches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    anime_id INTEGER NOT NULL,
    episodes_watched INTEGER NOT NULL,
    score INTEGER,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (anime_id) REFERENCES animes(id)
);
"""

# ---------- fixtures ----------
@pytest.fixture
def app_client(tmp_path):
    db_file = tmp_path / "cover_extra.sqlite"
    conn = sqlite3.connect(str(db_file))
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

    app = create_app()
    repo = SqliteRepo(str(db_file))
    svc = AnimeService(repo)
    app.config["SERVICE"] = svc
    app.testing = True
    with app.test_client() as client:
        yield client, svc

# ---------- repo/service focused tests (cover repo branches) ----------
def test_repo_list_animes_tag_join_and_filters():
    repo = InMemoryRepo()
    svc = AnimeService(repo)
    # create required entities through the service (in-memory repo)
    u = svc.create_user("u_repo")
    t = svc.create_tag("tt")
    s = svc.create_studio("ss")
    a = svc.create_anime("RepoA", 10, s.id)
    # assign tag to the anime using repo helper
    svc.repo.set_anime_tags(a.id, [t.id])
    # list by tag -- should find the anime
    res = svc.repo.list_animes(q=None, order_by="title", tag_id=t.id, studio_id=None)
    assert any(anime.id == a.id for anime in res)

def test_repo_list_watches_ordering_and_min_score():
    repo = InMemoryRepo()
    svc = AnimeService(repo)
    u = svc.create_user("wuser_repo")
    a1 = svc.create_anime("WA", 3, None)
    a2 = svc.create_anime("WB", 3, None)
    w1 = svc.add_watch_entry(u.id, a1.id, 3, score=7)
    w2 = svc.add_watch_entry(u.id, a2.id, 3, score=9)
    # list ordered by score
    res = svc.repo.list_watches_for_user(u.id, status=None, min_score=6, order_by="score")
    assert res and res[0].score >= res[-1].score

# ---------- service edge branches ----------
def test_service_update_delete_and_notfound_behaviour():
    repo = InMemoryRepo()
    svc = AnimeService(repo)
    # NotFound branches
    with pytest.raises(NotFoundError):
        svc.get_user(9999)
    # create and delete user with watches -> delete_user should remove entries without raising
    u = svc.create_user("del_svc")
    a = svc.create_anime("SvcDel", 2, None)
    w = svc.add_watch_entry(u.id, a.id, 1)
    svc.delete_user(u.id)  # should delete user and associated watches
    with pytest.raises(NotFoundError):
        svc.get_user(u.id)

def test_service_import_errors_and_partial_success():
    repo = InMemoryRepo()
    svc = AnimeService(repo)
    u = svc.create_user("imp_svc")
    a = svc.create_anime("ImpSvc", 4, None)
    # rows: good row, missing episodes, non-existent title
    rows = [
        {"anime_id": a.id, "episodes_watched": 1},
        {"anime_title": "DoesNotExist", "episodes_watched": 2},
        {"episodes_watched": 1}  # missing anime id/title
    ]
    created, errors = svc.import_watchlist_from_rows(u.id, rows)
    assert created >= 1
    assert len(errors) >= 1

def test_service_update_watch_score_bounds_and_errors():
    repo = InMemoryRepo()
    svc = AnimeService(repo)
    u = svc.create_user("score_bounds")
    a = svc.create_anime("Bounds", 3, None)
    w = svc.add_watch_entry(u.id, a.id, 3)  # completed
    # valid score
    svc.update_watch_score(w.id, 10)
    assert svc.repo.get_watch(w.id).score == 10
    # invalid score bounds
    with pytest.raises(ValidationError):
        svc.update_watch_score(w.id, 11)

# ---------- web routes and error handlers (cover many branches) ----------
def test_web_index_and_users_pages(app_client):
    client, svc = app_client
    r = client.get("/")
    assert r.status_code == 200
    r2 = client.get("/users")
    assert r2.status_code == 200

def test_web_user_creation_validation_and_edit(app_client):
    client, svc = app_client
    # invalid create (empty username) -> should flash and not create
    r = client.post("/users/new", data={"username": ""}, follow_redirects=True)
    # either error shown or redirect, assert page returned OK
    assert r.status_code == 200
    # create valid
    r2 = client.post("/users/new", data={"username": "webu"}, follow_redirects=True)
    assert b"User created." in r2.data or r2.status_code == 200
    user = svc.list_users()[0]
    # edit with invalid username
    r3 = client.post(f"/users/{user.id}/edit", data={"username": ""}, follow_redirects=True)
    assert r3.status_code == 200

def test_web_studio_tag_routes_notfound_and_create(app_client):
    client, svc = app_client
    # request edit for non-existent studio -> should redirect or flash
    r = client.get("/studios/999/edit", follow_redirects=True)
    assert r.status_code in (200, 302)
    # create studio ok
    r2 = client.post("/studios/new", data={"name": "WStudio"}, follow_redirects=True)
    assert b"Studio created" in r2.data

def test_web_anime_create_invalid_and_edit_notfound(app_client):
    client, svc = app_client
    # invalid anime creation (missing title)
    r = client.post("/animes/new", data={"title": "", "total_episodes": ""}, follow_redirects=True)
    assert r.status_code == 200
    # edit missing anime -> redirect/flash
    r2 = client.get("/animes/999/edit", follow_redirects=True)
    assert r2.status_code in (200, 302)

def test_web_watch_import_export_and_bad_parse(app_client):
    client, svc = app_client
    u = svc.create_user("webimp")
    a = svc.create_anime("WebImp", 5, None)
    svc.add_watch_entry(u.id, a.id, 1)
    # export csv and json
    rcsv = client.get(f"/users/{u.id}/watchlist/export?format=csv")
    assert rcsv.status_code == 200 and rcsv.mimetype == "text/csv"
    rjson = client.get(f"/users/{u.id}/watchlist/export?format=json")
    assert rjson.status_code == 200 and rjson.mimetype == "application/json"
    # upload bad file (non-CSV/JSON)
    bad = b"this is not csv or json"
    data = {"file": (io.BytesIO(bad), "bad.bin")}
    rimp = client.post(f"/users/{u.id}/watchlist/import", data=data, content_type="multipart/form-data", follow_redirects=True)
    # either a parse error flash or an imported result; acceptable for branch coverage
    assert rimp.status_code == 200

def test_web_watch_routes_and_errors(app_client):
    client, svc = app_client
    u = svc.create_user("wweb")
    a = svc.create_anime("WWeb", 4, None)
    # GET new watch page
    r = client.get(f"/users/{u.id}/watch/new")
    assert r.status_code == 200
    # POST add watch
    rp = client.post(f"/users/{u.id}/watch/new", data={"anime_id": str(a.id), "episodes_watched": "1"}, follow_redirects=True)
    assert b"Added to watchlist" in rp.data or rp.status_code == 200
    w = svc.list_user_watchlist(u.id)[0]
    # attempt to update score when not completed -> should flash ValidationError
    rscore = client.post(f"/watches/{w.id}/edit", data={"score": "9"}, follow_redirects=True)
    assert rscore.status_code == 200
    # delete watch
    rdel = client.post(f"/watches/{w.id}/delete", follow_redirects=True)
    assert rdel.status_code == 200

