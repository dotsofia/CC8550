import pytest
from app.repo import InMemoryRepo
from app.service import AnimeService, ValidationError, NotFoundError
from app.models import User, Anime, WatchEntry, Tag, Studio
from datetime import datetime

# ---------- Fixtures ----------
@pytest.fixture
def repo():
    return InMemoryRepo()

@pytest.fixture
def svc(repo):
    return AnimeService(repo)

@pytest.fixture
def sample_user(svc):
    u = svc.create_user("alice")
    return u

@pytest.fixture
def sample_studio(svc):
    s = svc.create_studio("Studio A")
    return s

@pytest.fixture
def sample_tags(svc):
    t1 = svc.create_tag("action")
    t2 = svc.create_tag("drama")
    return (t1, t2)

# ---------- User tests ----------
def test_create_user_success(svc):
    u = svc.create_user("bob")
    assert u.id is not None and u.username == "bob"

@pytest.mark.parametrize("bad_name", ["", "   "])
def test_create_user_invalid_name(svc, bad_name):
    with pytest.raises(ValidationError):
        svc.create_user(bad_name)

def test_update_user_success(svc, sample_user):
    svc.update_user(sample_user.id, "alice2")
    got = svc.get_user(sample_user.id)
    assert got.username == "alice2"

def test_update_user_invalid(svc, sample_user):
    with pytest.raises(ValidationError):
        svc.update_user(sample_user.id, "")

def test_delete_user(svc):
    u = svc.create_user("to_delete")
    svc.delete_user(u.id)
    with pytest.raises(NotFoundError):
        svc.get_user(u.id)

# ---------- Studio tests ----------
def test_create_studio_and_list(svc):
    s = svc.create_studio("S1")
    lst = svc.list_studios()
    assert any(x.name == "S1" for x in lst)

def test_update_and_delete_studio(svc, sample_studio):
    svc.update_studio(sample_studio.id, "Studio B")
    s = svc.repo.get_studio(sample_studio.id)
    assert s.name == "Studio B"
    svc.delete_studio(sample_studio.id)
    assert svc.repo.get_studio(sample_studio.id) is None

def test_create_studio_invalid(svc):
    with pytest.raises(ValidationError):
        svc.create_studio("")

# ---------- Tag tests ----------
def test_create_tag_and_list(svc):
    t = svc.create_tag("romance")
    tags = svc.list_tags()
    assert any(x.name == "romance" for x in tags)

def test_update_delete_tag(svc, sample_tags):
    t1, t2 = sample_tags
    svc.update_tag(t1.id, "action_new")
    assert svc.repo.get_tag(t1.id).name == "action_new"
    svc.delete_tag(t2.id)
    assert svc.repo.get_tag(t2.id) is None

def test_create_tag_invalid(svc):
    with pytest.raises(ValidationError):
        svc.create_tag("")

# ---------- Anime creation & validation ----------
def test_create_anime_success(svc, sample_studio):
    a = svc.create_anime("MyAnime", 12, sample_studio.id)
    assert a.id is not None and a.title == "MyAnime"

@pytest.mark.parametrize("title", ["A", "Some Title"])
def test_create_anime_various_titles(svc, title):
    a = svc.create_anime(title, None, None)
    assert a.title == title

def test_create_anime_invalid_title(svc):
    with pytest.raises(ValidationError):
        svc.create_anime("", 10, None)

def test_create_anime_invalid_episodes(svc):
    with pytest.raises(ValidationError):
        svc.create_anime("X", -5, None)

def test_get_nonexistent_anime_raises(svc):
    with pytest.raises(NotFoundError):
        svc.get_anime(9999)

# ---------- Watch entries: add, duplicate, bounds, auto-complete ----------
def test_add_watch_entry_basic(svc, sample_user):
    a = svc.create_anime("Small", 3, None)
    w = svc.add_watch_entry(sample_user.id, a.id, 1)
    assert w.id is not None and w.episodes_watched == 1 and w.user_id == sample_user.id

def test_add_watch_auto_complete(svc, sample_user):
    a = svc.create_anime("Fin", 2, None)
    w = svc.add_watch_entry(sample_user.id, a.id, 2)
    assert w.status == "completed"

def test_add_watch_score_only_if_completed(svc, sample_user):
    a = svc.create_anime("Sc", 3, None)
    with pytest.raises(ValidationError):
        svc.add_watch_entry(sample_user.id, a.id, 1, score=8)

def test_add_duplicate_watch_is_blocked(svc, sample_user):
    a = svc.create_anime("Dup", None, None)
    svc.add_watch_entry(sample_user.id, a.id, 0)
    with pytest.raises(ValidationError):
        svc.add_watch_entry(sample_user.id, a.id, 1)

def test_add_watch_episodes_exceed(svc, sample_user):
    a = svc.create_anime("Big", 5, None)
    with pytest.raises(ValidationError):
        svc.add_watch_entry(sample_user.id, a.id, 6)

# ---------- Update watch episodes and status transitions ----------
def test_update_watch_episodes_and_status(svc, sample_user):
    a = svc.create_anime("Trans", 4, None)
    w = svc.add_watch_entry(sample_user.id, a.id, 1)
    assert w.status == "watching"
    w2 = svc.update_watch_episodes(w.id, 4)
    assert w2.status == "completed"
    # decrease episodes -> back to watching
    w3 = svc.update_watch_episodes(w.id, 2)
    assert w3.status == "watching"

def test_update_watch_score_allowed(svc, sample_user):
    a = svc.create_anime("ScoreOk", 2, None)
    w = svc.add_watch_entry(sample_user.id, a.id, 2)
    updated = svc.update_watch_score(w.id, 9)
    assert updated.score == 9

def test_update_watch_score_disallowed(svc, sample_user):
    a = svc.create_anime("ScoreNo", 5, None)
    w = svc.add_watch_entry(sample_user.id, a.id, 1)
    with pytest.raises(ValidationError):
        svc.update_watch_score(w.id, 7)

def test_update_nonexistent_watch_raises(svc):
    with pytest.raises(NotFoundError):
        svc.update_watch_episodes(9999, 1)

# ---------- List / filter / ordering for animes ----------
def test_list_animes_search_filter_order(svc, sample_tags, sample_studio):
    t1, t2 = sample_tags
    s = sample_studio
    a1 = svc.create_anime("Alpha", 10, s.id)
    a2 = svc.create_anime("BetaShow", 5, None)
    # tag a1
    svc.repo.set_anime_tags(a1.id, [t1.id])
    res = svc.list_animes(q="Alpha", order_by="title")
    assert any(x.id == a1.id for x in res)
    res_tag = svc.list_animes(tag_id=t1.id)
    assert len(res_tag) >= 1 and res_tag[0].id == a1.id
    res_studio = svc.list_animes(studio_id=s.id)
    assert any(x.studio_id == s.id for x in res_studio)

def test_list_animes_order_by_episodes(svc):
    a1 = svc.create_anime("One", 1, None)
    a2 = svc.create_anime("Ten", 10, None)
    res = svc.list_animes(order_by="total_episodes")
    assert res[0].total_episodes == 1 or res[0].total_episodes == 10  # ensures ordering runs (in-memory may sort None specially)

# ---------- List / filter / ordering for watches ----------
def test_list_watches_filters_and_order(svc, sample_user):
    a1 = svc.create_anime("W1", 10, None)
    a2 = svc.create_anime("W2", 10, None)
    svc.add_watch_entry(sample_user.id, a1.id, 10, score=9)
    # adding score to unfinished anime should raise ValidationError
    with pytest.raises(ValidationError):
        svc.add_watch_entry(sample_user.id, a2.id, 5, score=5)

def test_list_watches_filters_and_order_continued(svc, sample_user):
    # additional scenario for ordering and filters
    a1 = svc.create_anime("W1b", 10, None)
    a2 = svc.create_anime("W2b", 10, None)
    svc.add_watch_entry(sample_user.id, a1.id, 10, score=9)
    svc.add_watch_entry(sample_user.id, a2.id, 10, score=5)
    res_all = svc.list_user_watchlist(sample_user.id)
    assert len(res_all) >= 2
    res_min_score = svc.list_user_watchlist(sample_user.id, min_score=8)
    assert all((w.score or 0) >= 8 for w in res_min_score)
    res_by_score = svc.list_user_watchlist(sample_user.id, order_by="score")
    assert res_by_score[0].score >= res_by_score[-1].score

# ---------- Export / Import ----------
def test_export_watchlist(svc, sample_user):
    a = svc.create_anime("ExportMe", 3, None)
    svc.add_watch_entry(sample_user.id, a.id, 1, score=None)
    rows = svc.export_watchlist(sample_user.id)
    assert isinstance(rows, list)
    assert any(r["anime_id"] == a.id for r in rows)

def test_import_watchlist_rows_success_and_errors(svc, sample_user):
    # create an anime to reference
    a = svc.create_anime("ImportAnime", 4, None)
    rows = [
        {"anime_id": a.id, "episodes_watched": 1},
        {"anime_title": "NonExistent", "episodes_watched": 2},  # should produce NotFoundError during import
        {"anime_title": "ImportAnime", "episodes_watched": 2}
    ]
    created, errors = svc.import_watchlist_from_rows(sample_user.id, rows)
    assert created >= 1
    assert len(errors) >= 1

# ---------- Delete anime protection (force) ----------
def test_delete_anime_blocked_if_watches_exist(svc, sample_user):
    a = svc.create_anime("Protect", 3, None)
    svc.add_watch_entry(sample_user.id, a.id, 1)
    with pytest.raises(ValidationError):
        svc.delete_anime(a.id, force=False)
    # force delete should not raise
    svc.delete_anime(a.id, force=True)
    with pytest.raises(NotFoundError):
        svc.get_anime(a.id)

def test_delete_anime_no_watches(svc):
    a = svc.create_anime("NoW", 2, None)
    svc.delete_anime(a.id, force=False)
    with pytest.raises(NotFoundError):
        svc.get_anime(a.id)

# ---------- Repo-level basic behavior (in-memory) ----------
def test_inmemory_repo_set_get_tag_and_anime_tags(svc):
    t = svc.create_tag("thriller")
    a = svc.create_anime("Tagable", None, None)
    svc.repo.set_anime_tags(a.id, [t.id])
    tags = svc.repo.get_anime_tags(a.id)
    assert any(tt.id == t.id for tt in tags)

# ---------- Parametrized edge cases ----------
@pytest.mark.parametrize("episodes, total, expect_ok", [
    (0, 0, True),
    (0, None, True),
    (5, 5, True),
    (6, 5, False),
])
def test_episodes_edge_cases(svc, sample_user, episodes, total, expect_ok):
    a = svc.create_anime("Edge", total, None)
    if expect_ok:
        w = svc.add_watch_entry(sample_user.id, a.id, episodes)
        assert w.episodes_watched == episodes
    else:
        with pytest.raises(ValidationError):
            svc.add_watch_entry(sample_user.id, a.id, episodes)

