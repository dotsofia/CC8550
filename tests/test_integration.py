import os
import sqlite3
import json
import csv
import io
import tempfile
import pytest

from app.repo import SqliteRepo
from app.service import AnimeService, ValidationError, NotFoundError

# --- Schema used for initializing the test database ---
SCHEMA_SQL = """
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

# --- Fixtures ------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    """Temporary SQLite database path"""
    p = tmp_path / "test_db.sqlite"
    return str(p)

@pytest.fixture
def repo_and_service(db_path):
    """Initialize SQLite schema and return repo + service"""
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    repo = SqliteRepo(db_path)
    svc = AnimeService(repo)
    return repo, svc

# --- Integration tests ---------------------------------------------------

def test_create_user_anime_and_watch_persist(repo_and_service):
    repo, svc = repo_and_service
    u = svc.create_user("int_alice")
    s = svc.create_studio("IntStudio")
    a = svc.create_anime("IntAnime", 5, s.id)
    w = svc.add_watch_entry(u.id, a.id, 1)
    assert repo.get_user(u.id).username == "int_alice"
    assert repo.get_anime(a.id).title == "IntAnime"
    assert repo.get_watch(w.id).episodes_watched == 1

def test_persistence_across_service_instances(tmp_path):
    """Data created in one service instance must persist for another."""
    db_file = tmp_path / "persist.sqlite"
    conn = sqlite3.connect(db_file)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()

    repo1 = SqliteRepo(str(db_file))
    svc1 = AnimeService(repo1)
    u = svc1.create_user("persist_user")
    a = svc1.create_anime("PersistAnime", 3, None)
    svc1.add_watch_entry(u.id, a.id, 2)

    # new service reading same DB
    repo2 = SqliteRepo(str(db_file))
    svc2 = AnimeService(repo2)
    users = svc2.list_users()
    assert any(x.username == "persist_user" for x in users)
    animes = svc2.list_animes(q="PersistAnime")
    assert any(x.title == "PersistAnime" for x in animes)

def test_import_export_workflow(repo_and_service, tmp_path):
    repo, svc = repo_and_service
    u = svc.create_user("imp_user")
    a1 = svc.create_anime("ImpA", 4, None)
    a2 = svc.create_anime("ImpB", 6, None)
    svc.add_watch_entry(u.id, a1.id, 1)
    svc.add_watch_entry(u.id, a2.id, 6, score=8)

    rows = svc.export_watchlist(u.id)
    assert isinstance(rows, list)

    json_path = tmp_path / "wl.json"
    json_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    # import to a new user
    u2 = svc.create_user("imp_user2")
    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    created, errors = svc.import_watchlist_from_rows(u2.id, parsed)
    assert created >= 1
    assert isinstance(errors, list)

def test_delete_anime_block_and_force(repo_and_service):
    repo, svc = repo_and_service
    u = svc.create_user("del_user")
    a = svc.create_anime("DelMe", 2, None)
    svc.add_watch_entry(u.id, a.id, 1)
    with pytest.raises(ValidationError):
        svc.delete_anime(a.id, force=False)
    svc.delete_anime(a.id, force=True)
    with pytest.raises(NotFoundError):
        svc.get_anime(a.id)

def test_tag_and_studio_crud(repo_and_service):
    repo, svc = repo_and_service
    s = svc.create_studio("TStudio")
    t = svc.create_tag("ttag")
    a = svc.create_anime("TiedAnime", None, s.id)
    svc.repo.set_anime_tags(a.id, [t.id])
    tags = svc.repo.get_anime_tags(a.id)
    assert any(x.name == "ttag" for x in tags)
    svc.update_studio(s.id, "TStudio2")
    svc.update_tag(t.id, "ttag2")
    assert svc.repo.get_studio(s.id).name == "TStudio2"
    assert svc.repo.get_tag(t.id).name == "ttag2"

def test_watch_updates_and_score_rules(repo_and_service):
    repo, svc = repo_and_service
    u = svc.create_user("upd_user")
    a = svc.create_anime("UpdAnime", 3, None)
    w = svc.add_watch_entry(u.id, a.id, 1)
    svc.update_watch_episodes(w.id, 3)
    got = svc.repo.get_watch(w.id)
    assert got.status == "completed"

    a2 = svc.create_anime("UpdAnime2", 5, None)
    w2 = svc.add_watch_entry(u.id, a2.id, 1)
    with pytest.raises(ValidationError):
        svc.update_watch_score(w2.id, 7)
    svc.update_watch_episodes(w2.id, 5)
    svc.update_watch_score(w2.id, 8)
    assert svc.repo.get_watch(w2.id).score == 8

def test_filters_and_orders_in_db(repo_and_service):
    repo, svc = repo_and_service
    u = svc.create_user("filter_user")
    s = svc.create_studio("FilterStudio")
    t = svc.create_tag("filtertag")
    a1 = svc.create_anime("FilterA", 10, s.id)
    a2 = svc.create_anime("FilterB", 5, None)
    svc.repo.set_anime_tags(a1.id, [t.id])
    res_tag = svc.list_animes(tag_id=t.id)
    assert any(a.id == a1.id for a in res_tag)
    res_order = svc.list_animes(order_by="total_episodes")
    assert len(res_order) >= 2

def test_import_rows_with_title_resolution(repo_and_service):
    repo, svc = repo_and_service
    u = svc.create_user("resolve_user")
    a = svc.create_anime("ResolveMe", 4, None)
    rows = [{"anime_title": "ResolveMe", "episodes_watched": 2}]
    created, errors = svc.import_watchlist_from_rows(u.id, rows)
    assert created == 1
    assert len(errors) == 0

def test_error_cases_on_integration(repo_and_service):
    repo, svc = repo_and_service
    with pytest.raises(NotFoundError):
        svc.export_watchlist(9999)
    with pytest.raises(NotFoundError):
        svc.import_watchlist_from_rows(9999, [])
    with pytest.raises(NotFoundError):
        svc.get_anime(99999)

def test_full_end_to_end_workflow(repo_and_service):
    """Full flow: create entities → link → watch → export → cleanup."""
    repo, svc = repo_and_service

    # Create everything
    user = svc.create_user("flow_user")
    studio = svc.create_studio("FlowStudio")
    tag = svc.create_tag("FlowTag")
    anime = svc.create_anime("FlowAnime", 12, studio.id)
    svc.repo.set_anime_tags(anime.id, [tag.id])

    # Watch progress
    watch = svc.add_watch_entry(user.id, anime.id, 6)
    svc.update_watch_episodes(watch.id, 12)
    svc.update_watch_score(watch.id, 9)

    # Export + verify contents
    exported = svc.export_watchlist(user.id)
    assert isinstance(exported, list)
    assert any(r["anime_id"] == anime.id and r["score"] == 9 for r in exported)

    # Delete anime (force) and confirm deletion
    svc.delete_anime(anime.id, force=True)
    with pytest.raises(NotFoundError):
        svc.get_anime(anime.id)

    # User still exists
    assert repo.get_user(user.id).username == "flow_user"

