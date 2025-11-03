import pytest
from app.service import AnimeService, ValidationError, NotFoundError
from app.repo import InMemoryRepo

@pytest.fixture
def svc():
    return AnimeService(InMemoryRepo())

def test_add_watch_entry_raises_for_invalid_user(svc):
    a = svc.create_anime("ErrorAnime", 3, None)
    with pytest.raises(NotFoundError, match="user not found"):
        svc.add_watch_entry(999, a.id, 1)

def test_add_watch_entry_raises_for_invalid_anime(svc):
    u = svc.create_user("ErrUser")
    with pytest.raises(NotFoundError, match="anime not found"):
        svc.add_watch_entry(u.id, 999, 1)

def test_add_watch_entry_negative_episodes(svc):
    u = svc.create_user("neg_user")
    a = svc.create_anime("NegAnime", 10, None)
    with pytest.raises(ValidationError, match="episodes_watched must be >= 0"):
        svc.add_watch_entry(u.id, a.id, -1)

def test_add_watch_entry_score_not_completed(svc):
    u = svc.create_user("score_user")
    a = svc.create_anime("NotDone", 12, None)
    # Expect the service to reject attempts to add a score for a non-completed entry
    # Match the exact message produced by add_watch_entry:
    with pytest.raises(ValidationError, match="score allowed only when completed"):
        svc.add_watch_entry(u.id, a.id, 5, score=9)

def test_delete_anime_blocked_by_watch_entry(svc):
    u = svc.create_user("blocked_user")
    a = svc.create_anime("BlockAnime", 3, None)
    svc.add_watch_entry(u.id, a.id, 1)
    with pytest.raises(ValidationError, match="has watch entries"):
        svc.delete_anime(a.id)

def test_update_watch_score_requires_completed(svc):
    u = svc.create_user("complete_user")
    a = svc.create_anime("CompAnime", 6, None)
    w = svc.add_watch_entry(u.id, a.id, 3)
    with pytest.raises(ValidationError, match="score only allowed when status is completed"):
        svc.update_watch_score(w.id, 8)

