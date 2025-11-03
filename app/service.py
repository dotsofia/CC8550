# app/service.py
from typing import List, Optional, Tuple
from app.models import User, Anime, WatchEntry, Tag, Studio
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# Exceptions
class ValidationError(Exception):
    """Raised when input or business validation fails."""
    pass

class NotFoundError(Exception):
    """Raised when an entity is not found."""
    pass

class AnimeService:
    """
    Business logic service for the anime tracker.
    The service expects a repository object exposing the methods used below
    (SqliteRepo or InMemoryRepo from app.repo).
    """

    def __init__(self, repo):
        """
        Initialize service with a repository instance (injected).
        """
        self.repo = repo
        logger.debug("AnimeService initialized with repo %s", type(repo).__name__)

    # ---- Users ----
    def create_user(self, username: str) -> User:
        """Create a new user. Username must be non-empty."""
        if not username or len(username.strip()) < 1:
            logger.warning("create_user: invalid username provided")
            raise ValidationError("username required")
        u = User(id=None, username=username.strip())
        created = self.repo.create_user(u)
        logger.info("Created user id=%s username=%s", created.id, created.username)
        return created

    def list_users(self) -> List[User]:
        """Return list of users."""
        return self.repo.list_users()

    def get_user(self, user_id: int) -> User:
        """Get a user by id or raise NotFoundError."""
        u = self.repo.get_user(user_id)
        if not u:
            logger.debug("get_user: user %s not found", user_id)
            raise NotFoundError("user not found")
        return u

    def update_user(self, user_id: int, username: str) -> None:
        """Update username for user_id."""
        u = self.get_user(user_id)
        if not username or len(username.strip()) == 0:
            logger.warning("update_user: invalid username for user %s", user_id)
            raise ValidationError("username required")
        u.username = username.strip()
        self.repo.update_user(u)
        logger.info("Updated user id=%s username=%s", user_id, u.username)

    def delete_user(self, user_id: int) -> None:
        """Delete user (and their watches via repo logic)."""
        self.repo.delete_user(user_id)
        logger.info("Deleted user id=%s", user_id)

    # ---- Studios ----
    def create_studio(self, name: str) -> Studio:
        """Create a studio with a non-empty name."""
        if not name or len(name.strip()) == 0:
            logger.warning("create_studio: invalid name")
            raise ValidationError("studio name required")
        s = Studio(id=None, name=name.strip())
        created = self.repo.create_studio(s)
        logger.info("Created studio id=%s name=%s", created.id, created.name)
        return created

    def list_studios(self) -> List[Studio]:
        return self.repo.list_studios()

    def update_studio(self, sid: int, name: str) -> None:
        s = self.repo.get_studio(sid)
        if not s:
            logger.debug("update_studio: studio %s not found", sid)
            raise NotFoundError("studio not found")
        if not name or len(name.strip()) == 0:
            raise ValidationError("studio name required")
        s.name = name.strip()
        self.repo.update_studio(s)
        logger.info("Updated studio id=%s", sid)

    def delete_studio(self, sid: int) -> None:
        self.repo.delete_studio(sid)
        logger.info("Deleted studio id=%s", sid)

    # ---- Tags ----
    def create_tag(self, name: str) -> Tag:
        """Create tag (non-empty)."""
        if not name or len(name.strip()) == 0:
            raise ValidationError("tag name required")
        t = Tag(id=None, name=name.strip())
        created = self.repo.create_tag(t)
        logger.info("Created tag id=%s name=%s", created.id, created.name)
        return created

    def list_tags(self) -> List[Tag]:
        return self.repo.list_tags()

    def update_tag(self, tid: int, name: str) -> None:
        t = self.repo.get_tag(tid)
        if not t:
            raise NotFoundError("tag not found")
        if not name or len(name.strip()) == 0:
            raise ValidationError("tag name required")
        t.name = name.strip()
        self.repo.update_tag(t)
        logger.info("Updated tag id=%s", tid)

    def delete_tag(self, tid: int) -> None:
        self.repo.delete_tag(tid)
        logger.info("Deleted tag id=%s", tid)

    # ---- Animes ----
    def create_anime(self, title: str, total_episodes: Optional[int], studio_id: Optional[int]) -> Anime:
        """Create an anime. Title required; total_episodes must be non-negative or None."""
        if not title or not title.strip():
            raise ValidationError("title required")
        if total_episodes is not None and total_episodes < 0:
            raise ValidationError("invalid total_episodes")
        a = Anime(id=None, title=title.strip(), total_episodes=total_episodes, studio_id=studio_id)
        created = self.repo.create_anime(a)
        logger.info("Created anime id=%s title=%s", created.id, created.title)
        return created

    def list_animes(self, q: Optional[str] = None, order_by: str = "title", tag_id: Optional[int] = None, studio_id: Optional[int] = None) -> List[Anime]:
        """List animes optionally filtered by title, tag, studio and ordered by a safe column."""
        return self.repo.list_animes(q=q, order_by=order_by, tag_id=tag_id, studio_id=studio_id)


    def get_anime(self, anime_id: int) -> Anime:
        a = self.repo.get_anime(anime_id)
        if not a:
            raise NotFoundError("anime not found")
        return a

    def update_anime(self, anime_id: int, title: str, total_episodes: Optional[int],
                     studio_id: Optional[int], tag_ids: List[int]) -> None:
        a = self.get_anime(anime_id)
        if not title or len(title.strip()) == 0:
            raise ValidationError("title required")
        if total_episodes is not None and total_episodes < 0:
            raise ValidationError("invalid total_episodes")
        a.title = title.strip()
        a.total_episodes = total_episodes
        a.studio_id = studio_id
        self.repo.update_anime(a)
        self.repo.set_anime_tags(anime_id, tag_ids)
        logger.info("Updated anime id=%s", anime_id)

    def delete_anime(self, anime_id: int, force: bool = False) -> None:
        """
        Delete anime. If there are watch entries referencing the anime, require force=True.
        This implementation checks all users' watches (works with current repo methods).
        """
        # check for existing watch entries referencing anime
        found = False
        for u in self.repo.list_users():
            ws = self.repo.list_watches_for_user(u.id)
            for w in ws:
                if w.anime_id == anime_id:
                    found = True
                    break
            if found:
                break
        if found and not force:
            logger.warning("delete_anime blocked for anime_id=%s due to existing watches", anime_id)
            raise ValidationError("anime has watch entries; pass force=True to delete")
        self.repo.delete_anime(anime_id)
        logger.info("Deleted anime id=%s (force=%s)", anime_id, force)

    # ---- Watches ----
    def add_watch_entry(self, user_id: int, anime_id: int, episodes_watched: int,
                        score: Optional[int] = None, status: Optional[str] = None) -> WatchEntry:
        """
        Add a watch entry. Validations:
        - user and anime must exist
        - episodes_watched >= 0
        - cannot exceed anime.total_episodes if known
        - score only allowed when final status is 'completed'
        - cannot add a duplicate entry for same user+anime
        """
        if episodes_watched < 0:
            raise ValidationError("episodes_watched must be >= 0")
        user = self.repo.get_user(user_id)
        if not user:
            raise NotFoundError("user not found")
        anime = self.repo.get_anime(anime_id)
        if not anime:
            raise NotFoundError("anime not found")
        # Duplicate check: user already has this anime in their watchlist?
        existing = self.repo.list_watches_for_user(user_id)
        for w in existing:
            if w.anime_id == anime_id:
                logger.warning("Attempt to add duplicate watch entry user=%s anime=%s", user_id, anime_id)
                raise ValidationError("This anime is already in the user's watchlist")
        if anime.total_episodes is not None and episodes_watched > anime.total_episodes:
            logger.debug("add_watch_entry: episodes %s > total %s", episodes_watched, anime.total_episodes)
            raise ValidationError("episodes_watched cannot exceed total_episodes")

        final_status = status or ("completed" if (anime.total_episodes is not None and episodes_watched == anime.total_episodes) else "watching")
        if score is not None and final_status != "completed":
            raise ValidationError("score allowed only when completed")

        w = WatchEntry(id=None, user_id=user_id, anime_id=anime_id,
                    episodes_watched=episodes_watched, score=score, status=final_status, updated_at=now_iso())
        created = self.repo.create_watch(w)
        logger.info("Added watch id=%s user=%s anime=%s eps=%s", created.id, user_id, anime_id, episodes_watched)
        return created

    def update_watch_episodes(self, watch_id: int, episodes: int) -> WatchEntry:
        """Update episodes watched and apply auto-complete logic."""
        w = self.repo.get_watch(watch_id)
        if not w:
            raise NotFoundError("watch not found")
        anime = self.repo.get_anime(w.anime_id)
        if anime.total_episodes is not None and episodes > anime.total_episodes:
            raise ValidationError("episodes exceed anime total")
        w.episodes_watched = episodes
        if anime.total_episodes is not None and episodes == anime.total_episodes:
            w.status = "completed"
        elif w.status == "completed" and (anime.total_episodes is None or episodes < anime.total_episodes):
            w.status = "watching"
        w.updated_at = now_iso()
        self.repo.update_watch(w)
        logger.info("Updated watch id=%s episodes=%s status=%s", w.id, w.episodes_watched, w.status)
        return w

    def update_watch_score(self, watch_id: int, score: Optional[int]) -> WatchEntry:
        """Update score for a watch entry (allowed only when completed)."""
        w = self.repo.get_watch(watch_id)
        if not w:
            raise NotFoundError("watch not found")
        if score is not None and (score < 0 or score > 10):
            raise ValidationError("score must be 0-10")
        if score is not None and w.status != "completed":
            raise ValidationError("score only allowed when status is completed")
        w.score = score
        w.updated_at = now_iso()
        self.repo.update_watch(w)
        logger.info("Updated score for watch id=%s to %s", w.id, w.score)
        return w

    def list_user_watchlist(self, user_id: int, status: Optional[str] = None, min_score: Optional[int] = None, order_by: str = "updated_at") -> List[WatchEntry]:
        """List watch entries for a user; optional status filter, min_score filter and ordering."""
        return self.repo.list_watches_for_user(user_id, status=status, min_score=min_score, order_by=order_by)

    def delete_watch(self, watch_id: int) -> None:
        self.repo.delete_watch(watch_id)
        logger.info("Deleted watch id=%s", watch_id)

    # ---- Import / Export ----
    def export_watchlist(self, user_id: int) -> List[dict]:
        """
        Export user's watchlist as a list of dicts ready for JSON or CSV.
        Each dict: anime_title, anime_id, episodes_watched, score, status, updated_at
        """
        user = self.repo.get_user(user_id)
        if not user:
            raise NotFoundError("user not found")
        watches = self.repo.list_watches_for_user(user_id)
        out = []
        for w in watches:
            anime = self.repo.get_anime(w.anime_id)
            out.append({
                "anime_id": w.anime_id,
                "anime_title": anime.title if anime else "",
                "episodes_watched": w.episodes_watched,
                "score": w.score,
                "status": w.status,
                "updated_at": w.updated_at
            })
        logger.info("Exported %d watch entries for user %s", len(out), user_id)
        return out

    def import_watchlist_from_rows(self, user_id: int, rows: List[dict]) -> Tuple[int, List[str]]:
        """
        Import a list of watchlist rows (dicts). Accepts keys:
          anime_id OR anime_title, episodes_watched (required), score (opt), status (opt)
        Returns (created_count, errors)
        """
        user = self.repo.get_user(user_id)
        if not user:
            raise NotFoundError("user not found")
        created = 0
        errors: List[str] = []
        for i, r in enumerate(rows):
            try:
                anime_id = r.get("anime_id")
                if anime_id is None:
                    # try resolve by title
                    title = r.get("anime_title") or r.get("title")
                    if not title:
                        raise ValidationError("anime_id or anime_title required")
                    # find first matching anime
                    matches = [a for a in self.repo.list_animes(q=title) if a.title.lower() == title.lower()]
                    if matches:
                        anime_id = matches[0].id
                    else:
                        raise NotFoundError(f"anime with title '{title}' not found")
                episodes = int(r.get("episodes_watched", 0))
                score = r.get("score")
                score = int(score) if score not in (None, "", "null") else None
                status = r.get("status")
                self.add_watch_entry(user_id=user_id, anime_id=int(anime_id), episodes_watched=episodes,
                                     score=score, status=status)
                created += 1
            except Exception as e:
                msg = f"row {i+1}: {str(e)}"
                logger.warning("import row failed: %s", msg)
                errors.append(msg)
        logger.info("Import completed for user %s: created=%s errors=%d", user_id, created, len(errors))
        return created, errors

