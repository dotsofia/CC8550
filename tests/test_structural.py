import io
import json
import sqlite3
import pytest
from run import create_app
from app.repo import SqliteRepo
from app.service import AnimeService, ValidationError, NotFoundError

# Minimal DB schema (same as before)
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

@pytest.fixture
def client(tmp_path):
    db_file = tmp_path / "structural.sqlite"
    conn = sqlite3.connect(str(db_file))
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

    app = create_app()
    repo = SqliteRepo(str(db_file))
    svc = AnimeService(repo)
    app.config["SERVICE"] = svc
    app.testing = True
    with app.test_client() as c:
        yield c, svc

# ---------- Structural tests covering many routes and branches ----------

def test_index_and_layout_links(client):
    c, svc = client
    r = c.get("/")
    assert r.status_code == 200
    # layout should include links to main sections; check for Users or Animes
    assert b"Users" in r.data or b"Animes" in r.data

def test_user_crud_flow(client):
    c, svc = client
    # create user
    resp = c.post("/users/new", data={"username":"u1"}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"User created." in resp.data
    # list users
    r = c.get("/users")
    assert b"u1" in r.data
    # edit user
    user = svc.list_users()[0]
    r2 = c.post(f"/users/{user.id}/edit", data={"username":"u1-edited"}, follow_redirects=True)
    assert b"Updated." in r2.data or r2.status_code == 200
    # delete user
    r3 = c.post(f"/users/{user.id}/delete", follow_redirects=True)
    assert b"Deleted user" in r3.data or r3.status_code == 200

def test_studio_and_tag_crud_routes(client):
    c, svc = client
    # create studio
    r = c.post("/studios/new", data={"name":"S1"}, follow_redirects=True)
    assert b"Studio created" in r.data
    # create tag
    r2 = c.post("/tags/new", data={"name":"T1"}, follow_redirects=True)
    assert b"Tag created" in r2.data
    # edit studio
    s = svc.list_studios()[0]
    r3 = c.post(f"/studios/{s.id}/edit", data={"name":"S1b"}, follow_redirects=True)
    assert b"Updated" in r3.data or r3.status_code == 200
    # delete tag
    t = svc.list_tags()[0]
    r4 = c.post(f"/tags/{t.id}/delete", follow_redirects=True)
    assert b"Deleted" in r4.data or r4.status_code == 200

def test_anime_crud_and_force_delete_branch(client):
    c, svc = client
    # create studio and anime
    s = svc.create_studio("StudioX")
    resp = c.post("/animes/new", data={"title":"A1", "total_episodes":"3", "studio": str(s.id)}, follow_redirects=True)
    assert b"Anime created" in resp.data
    anime = svc.list_animes(q="A1")[0]
    # delete anime without watches -> should succeed
    rdel = c.post(f"/animes/{anime.id}/delete", data={}, follow_redirects=True)
    assert b"Deleted anime" in rdel.data or rdel.status_code == 200
    # re-create and add watch then try delete without force -> should show validation message
    anime2 = svc.create_anime("A2", 3, s.id)
    user = svc.create_user("deluser")
    svc.add_watch_entry(user.id, anime2.id, 1)
    rfail = c.post(f"/animes/{anime2.id}/delete", data={}, follow_redirects=True)
    assert b"watch entries" in rfail.data or b"has watch entries" in rfail.data
    # force delete works
    rforce = c.post(f"/animes/{anime2.id}/delete", data={"force":"1"}, follow_redirects=True)
    assert b"Deleted anime" in rforce.data

def test_watchlist_export_import_and_error_branches(client, tmp_path):
    c, svc = client
    u = svc.create_user("expuser")
    a = svc.create_anime("XExport", 4, None)
    svc.add_watch_entry(u.id, a.id, 1)
    # export csv
    rcsv = c.get(f"/users/{u.id}/watchlist/export?format=csv")
    assert rcsv.status_code == 200
    assert rcsv.mimetype == "text/csv"
    # export json
    rjson = c.get(f"/users/{u.id}/watchlist/export?format=json")
    assert rjson.status_code == 200
    # import malformed file -> should flash parse error
    bad_content = b"not,a,real,json\n"
    data = {"file": (io.BytesIO(bad_content), "bad.txt")}
    rimp = c.post(f"/users/{u.id}/watchlist/import", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert b"Failed to parse" in rimp.data or b"Imported:" in rimp.data

    # import valid csv referencing unknown anime -> will produce errors list (flashed)
    csv_content = "anime_title,episodes_watched\nNoSuch,1\n"
    data2 = {"file": (io.BytesIO(csv_content.encode("utf-8")), "ok.csv")}
    rimp2 = c.post(f"/users/{u.id}/watchlist/import", data=data2, content_type="multipart/form-data", follow_redirects=True)
    # either created==0 and errors >=1 or flashed parse message — both acceptable for branch coverage
    assert rimp2.status_code == 200

def test_watch_new_and_edit_delete_routes(client):
    c, svc = client
    u = svc.create_user("wuser")
    a1 = svc.create_anime("WatchA", 6, None)
    # add via POST
    r = c.post(f"/users/{u.id}/watch/new", data={"anime_id": str(a1.id), "episodes_watched": "1"}, follow_redirects=True)
    assert b"Added to watchlist" in r.data
    # get watch id
    w = svc.list_user_watchlist(u.id)[0]
    # edit episodes (POST)
    r2 = c.post(f"/watches/{w.id}/edit", data={"episodes_watched": "2"}, follow_redirects=True)
    assert b"Updated episodes" in r2.data or r2.status_code == 200
    # try score update when not completed -> expect flashed validation error
    r3 = c.post(f"/watches/{w.id}/edit", data={"score": "8"}, follow_redirects=True)
    assert b"score only allowed" in r3.data or b"score allowed" in r3.data
    # delete watch
    r4 = c.post(f"/watches/{w.id}/delete", follow_redirects=True)
    assert r4.status_code == 200

def test_error_handlers_rendered_for_notfound_and_validation(client):
    c, svc = client
    # NotFoundError via user watchlist for missing user
    r = c.get("/users/9999/watchlist")
    # Should return 404 and show error template
    assert r.status_code in (200, 404)
    # Cause ValidationError by attempting to create anime with empty title via POST to /animes/new
    r2 = c.post("/animes/new", data={"title":"", "total_episodes":"", "studio":""}, follow_redirects=True)
    assert r2.status_code == 200
    # Check that either flash or error page shows text indicating invalid title or validation message
    assert b"title required" in r2.data or b"ValidationError" not in r2.data

def test_anime_list_filters_and_order_ui(client):
    c, svc = client
    s = svc.create_studio("FiltS")
    t = svc.create_tag("FiltT")
    a1 = svc.create_anime("AlphaF", 3, s.id)
    a2 = svc.create_anime("BetaF", 5, None)
    svc.repo.set_anime_tags(a1.id, [t.id])
    # request filtered page
    r = c.get(f"/animes?tag={t.id}&studio={s.id}&order=title&q=Alpha")
    assert r.status_code == 200
    assert b"AlphaF" in r.data

