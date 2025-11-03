import io
import json
import sqlite3
import tempfile

import pytest
from run import create_app
from app.repo import SqliteRepo
from app.service import AnimeService, ValidationError, NotFoundError

# Minimal schema used by the app (same as scripts/init_db.py)
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
    # create temp sqlite db
    db_file = tmp_path / "functional.sqlite"
    conn = sqlite3.connect(str(db_file))
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

    # create app and override its SERVICE to use our temp DB
    app = create_app()
    repo = SqliteRepo(str(db_file))
    svc = AnimeService(repo)
    app.config["SERVICE"] = svc

    # Use testing mode and produce a client
    app.testing = True
    with app.test_client() as c:
        yield c

# ------------------ Functional scenarios (8) ------------------

def test_create_user_and_list(client):
    # create user via UI
    resp = client.post("/users/new", data={"username": "f_user"}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"User created." in resp.data

    # check users list shows the username
    resp2 = client.get("/users")
    assert b"f_user" in resp2.data

def test_create_studio_and_anime_and_search(client):
    # create studio directly via UI
    resp = client.post("/studios/new", data={"name": "FStudio"}, follow_redirects=True)
    assert b"Studio created" in resp.data

    # create anime via UI (studio id 1 in fresh DB)
    resp2 = client.post("/animes/new", data={"title": "FuncAnime", "total_episodes": "6", "studio": "1"}, follow_redirects=True)
    assert b"Anime created" in resp2.data

    # search by title
    resp3 = client.get("/animes?q=FuncAnime")
    assert b"FuncAnime" in resp3.data

def test_add_watch_and_prevent_duplicate(client):
    # prepare: create user and anime using server-side service (in app context)
    with client.application.app_context():
        svc = client.application.config["SERVICE"]
        u = svc.create_user("watch_user")
        a = svc.create_anime("WatchMe", 4, None)

    # add watch via UI
    resp = client.post(f"/users/{u.id}/watch/new", data={"anime_id": str(a.id), "episodes_watched": "1"}, follow_redirects=True)
    assert b"Added to watchlist" in resp.data

    # attempt duplicate add — should show a flashed ValidationError message
    resp2 = client.post(f"/users/{u.id}/watch/new", data={"anime_id": str(a.id), "episodes_watched": "2"}, follow_redirects=True)

    # Jinja escapes quotes, so assert presence of key substrings rather than exact punctuation
    assert (b"already in the" in resp2.data and b"watchlist" in resp2.data), \
        f"Expected duplicate message in response, got: {resp2.data[:400]!r}"

def test_export_csv_and_json_endpoints(client):
    with client.application.app_context():
        svc = client.application.config["SERVICE"]
        u = svc.create_user("export_user")
        a = svc.create_anime("ExportThis", 3, None)
        svc.add_watch_entry(u.id, a.id, 1)

    # CSV export
    resp = client.get(f"/users/{u.id}/watchlist/export?format=csv")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert b"anime_id" in resp.data  # header

    # JSON export
    resp2 = client.get(f"/users/{u.id}/watchlist/export?format=json")
    assert resp2.status_code == 200
    assert resp2.mimetype == "application/json"
    parsed = json.loads(resp2.data.decode("utf-8"))
    assert isinstance(parsed, list)
    assert any(item.get("anime_title") == "ExportThis" for item in parsed)

def test_import_csv_via_upload(client):
    with client.application.app_context():
        svc = client.application.config["SERVICE"]
        u = svc.create_user("import_user")
        # create the anime to be referenced by title
        a = svc.create_anime("ImportTarget", 5, None)

    # prepare CSV content with anime_title
    csv_content = "anime_title,episodes_watched,score\nImportTarget,2,7\n"
    data = {
        "file": (io.BytesIO(csv_content.encode("utf-8")), "watchlist.csv")
    }
    resp = client.post(f"/users/{u.id}/watchlist/import", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200
    # should flash import result
    assert b"Imported:" in resp.data

def test_delete_anime_blocked_and_force_delete(client):
    with client.application.app_context():
        svc = client.application.config["SERVICE"]
        u = svc.create_user("del_user_func")
        a = svc.create_anime("DelTest", 3, None)
        svc.add_watch_entry(u.id, a.id, 1)

    # try delete without force via UI
    resp = client.post(f"/animes/{a.id}/delete", data={}, follow_redirects=True)
    assert b"anime has watch entries" in resp.data

    # delete with force checkbox included
    resp2 = client.post(f"/animes/{a.id}/delete", data={"force": "1"}, follow_redirects=True)
    assert b"Deleted anime" in resp2.data

def test_update_score_only_when_completed_via_ui(client):
    with client.application.app_context():
        svc = client.application.config["SERVICE"]
        u = svc.create_user("score_user")
        a = svc.create_anime("ScoreFlow", 3, None)
        w = svc.add_watch_entry(u.id, a.id, 1)  # not completed

    # try to set score via the watch edit POST (should flash ValidationError)
    resp = client.post(f"/watches/{w.id}/edit", data={"score": "8"}, follow_redirects=True)
    assert b"score only allowed when status is completed" in resp.data

def test_search_and_filter_ui_combination(client):
    with client.application.app_context():
        svc = client.application.config["SERVICE"]
        # create studios/tags/animes
        s1 = svc.create_studio("S1")
        a1 = svc.create_anime("AlphaSearch", 10, s1.id)
        a2 = svc.create_anime("BetaSearch", 5, None)
    # filter by studio
    resp = client.get(f"/animes?studio={s1.id}")
    assert b"AlphaSearch" in resp.data

