# app/repo.py
import sqlite3
from typing import List, Optional, Tuple, Dict
from app.models import User, Anime, WatchEntry, Tag, Studio
import os
from contextlib import contextmanager

# --- Exceptions ---
class RepoError(Exception):
    pass

# --- SQLite repo ---
class SqliteRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    @contextmanager
    def conn(self):
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    # -- Users --
    def create_user(self, user: User) -> User:
        with self.conn() as c:
            cur = c.execute("INSERT INTO users (username, created_at) VALUES (?, ?)",
                            (user.username, user.created_at))
            user.id = cur.lastrowid
            return user

    def get_user(self, user_id: int) -> Optional[User]:
        with self.conn() as c:
            r = c.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return User(r["id"], r["username"], r["created_at"]) if r else None

    def list_users(self) -> List[User]:
        with self.conn() as c:
            rows = c.execute("SELECT * FROM users ORDER BY username").fetchall()
            return [User(r["id"], r["username"], r["created_at"]) for r in rows]

    def update_user(self, user: User) -> None:
        with self.conn() as c:
            c.execute("UPDATE users SET username = ? WHERE id = ?", (user.username, user.id))

    def delete_user(self, user_id: int) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM users WHERE id = ?", (user_id,))

    # -- Studios --
    def create_studio(self, s: Studio) -> Studio:
        with self.conn() as c:
            cur = c.execute("INSERT INTO studios (name, created_at) VALUES (?, ?)",
                            (s.name, s.created_at))
            s.id = cur.lastrowid
            return s

    def get_studio(self, studio_id: int) -> Optional[Studio]:
        with self.conn() as c:
            r = c.execute("SELECT * FROM studios WHERE id=?", (studio_id,)).fetchone()
            return Studio(r["id"], r["name"], r["created_at"]) if r else None

    def list_studios(self) -> List[Studio]:
        with self.conn() as c:
            rows = c.execute("SELECT * FROM studios ORDER BY name").fetchall()
            return [Studio(r["id"], r["name"], r["created_at"]) for r in rows]

    def update_studio(self, s: Studio) -> None:
        with self.conn() as c:
            c.execute("UPDATE studios SET name = ? WHERE id = ?", (s.name, s.id))

    def delete_studio(self, studio_id: int) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM studios WHERE id = ?", (studio_id,))

    # -- Tags --
    def create_tag(self, tag: Tag) -> Tag:
        with self.conn() as c:
            cur = c.execute("INSERT INTO tags (name) VALUES (?)", (tag.name,))
            tag.id = cur.lastrowid
            return tag

    def get_tag(self, tag_id: int) -> Optional[Tag]:
        with self.conn() as c:
            r = c.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()
            return Tag(r["id"], r["name"]) if r else None

    def list_tags(self) -> List[Tag]:
        with self.conn() as c:
            rows = c.execute("SELECT * FROM tags ORDER BY name").fetchall()
            return [Tag(r["id"], r["name"]) for r in rows]

    def update_tag(self, tag: Tag) -> None:
        with self.conn() as c:
            c.execute("UPDATE tags SET name = ? WHERE id = ?", (tag.name, tag.id))

    def delete_tag(self, tag_id: int) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
            c.execute("DELETE FROM anime_tags WHERE tag_id = ?", (tag_id,))

    # -- Animes --
    def create_anime(self, anime: Anime) -> Anime:
        with self.conn() as c:
            cur = c.execute("INSERT INTO animes (title, total_episodes, studio_id) VALUES (?, ?, ?)",
                            (anime.title, anime.total_episodes, anime.studio_id))
            anime.id = cur.lastrowid
            return anime

    def get_anime(self, anime_id: int) -> Optional[Anime]:
        with self.conn() as c:
            r = c.execute("SELECT * FROM animes WHERE id = ?", (anime_id,)).fetchone()
            return Anime(r["id"], r["title"], r["total_episodes"], r["studio_id"]) if r else None

    def list_animes(self, q: Optional[str] = None, order_by: str = "title", tag_id: Optional[int] = None, studio_id: Optional[int] = None) -> List[Anime]:
        """
        List animes filtered by title substring (q), tag_id, studio_id and ordered by a safe column.
        Allowed order_by: title, total_episodes, id
        """
        allowed = {"title": "title", "total_episodes": "total_episodes", "id": "id"}
        order_col = allowed.get(order_by, "title")
        params = []
        where_clauses = []
        sql = "SELECT DISTINCT a.* FROM animes a"
        # join for tags if needed
        if tag_id is not None:
            sql += " JOIN anime_tags at ON a.id = at.anime_id"
            where_clauses.append("at.tag_id = ?")
            params.append(tag_id)
        if q:
            where_clauses.append("a.title LIKE ?")
            params.append(f"%{q}%")
        if studio_id is not None:
            where_clauses.append("a.studio_id = ?")
            params.append(studio_id)
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)
        sql += f" ORDER BY {order_col} COLLATE NOCASE"
        with self.conn() as c:
            rows = c.execute(sql, tuple(params)).fetchall()
            return [Anime(r["id"], r["title"], r["total_episodes"], r["studio_id"]) for r in rows]

    def update_anime(self, anime: Anime) -> None:
        with self.conn() as c:
            c.execute("UPDATE animes SET title=?, total_episodes=?, studio_id=? WHERE id=?",
                      (anime.title, anime.total_episodes, anime.studio_id, anime.id))

    def delete_anime(self, anime_id: int) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM animes WHERE id = ?", (anime_id,))
            c.execute("DELETE FROM anime_tags WHERE anime_id = ?", (anime_id,))
            c.execute("DELETE FROM watches WHERE anime_id = ?", (anime_id,))

    def set_anime_tags(self, anime_id: int, tag_ids: List[int]) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM anime_tags WHERE anime_id = ?", (anime_id,))
            for tid in tag_ids:
                c.execute("INSERT INTO anime_tags (anime_id, tag_id) VALUES (?, ?)", (anime_id, tid))

    def get_anime_tags(self, anime_id: int) -> List[Tag]:
        with self.conn() as c:
            rows = c.execute(
                "SELECT t.id, t.name FROM tags t JOIN anime_tags at ON t.id=at.tag_id WHERE at.anime_id=?",
                (anime_id,)).fetchall()
            return [Tag(r["id"], r["name"]) for r in rows]

    # -- Watches --
    def create_watch(self, w: WatchEntry) -> WatchEntry:
        with self.conn() as c:
            cur = c.execute(
                "INSERT INTO watches (user_id, anime_id, episodes_watched, score, status, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (w.user_id, w.anime_id, w.episodes_watched, w.score, w.status, w.updated_at))
            w.id = cur.lastrowid
            return w

    def get_watch(self, watch_id: int) -> Optional[WatchEntry]:
        with self.conn() as c:
            r = c.execute("SELECT * FROM watches WHERE id = ?", (watch_id,)).fetchone()
            return WatchEntry(r["id"], r["user_id"], r["anime_id"], r["episodes_watched"],
                              r["score"], r["status"], r["updated_at"]) if r else None

    def list_watches_for_user(self, user_id: int, status: Optional[str] = None, min_score: Optional[int] = None, order_by: str = "updated_at") -> List[WatchEntry]:
        """
        List watches for a user with optional status filter, minimum score, and ordering.
        Allowed order_by: updated_at, score, episodes_watched
        """
        allowed = {"updated_at": "updated_at", "score": "score", "episodes_watched": "episodes_watched"}
        order_col = allowed.get(order_by, "updated_at")
        params = [user_id]
        where = ["user_id = ?"]
        if status:
            where.append("status = ?"); params.append(status)
        if min_score is not None:
            where.append("score >= ?"); params.append(min_score)
        sql = "SELECT * FROM watches WHERE " + " AND ".join(where) + f" ORDER BY {order_col} DESC"
        with self.conn() as c:
            rows = c.execute(sql, tuple(params)).fetchall()
            return [WatchEntry(r["id"], r["user_id"], r["anime_id"], r["episodes_watched"], r["score"], r["status"], r["updated_at"]) for r in rows]

    def update_watch(self, w: WatchEntry) -> None:
        with self.conn() as c:
            c.execute("UPDATE watches SET episodes_watched=?, score=?, status=?, updated_at=? WHERE id=?",
                      (w.episodes_watched, w.score, w.status, w.updated_at, w.id))

    def delete_watch(self, watch_id: int) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM watches WHERE id = ?", (watch_id,))

# --- In-memory repo (simple, used for unit tests) ---
class InMemoryRepo:
    def __init__(self):
        self._users: Dict[int, User] = {}
        self._animes: Dict[int, Anime] = {}
        self._watches: Dict[int, WatchEntry] = {}
        self._tags: Dict[int, Tag] = {}
        self._studios: Dict[int, Studio] = {}
        self._anime_tags: Dict[int, List[int]] = {}
        self._next = {"user": 1, "anime": 1, "watch": 1, "tag": 1, "studio": 1}

    # helper to assign id
    def _assign(self, kind: str) -> int:
        nid = self._next[kind]
        self._next[kind] += 1
        return nid

    # Users
    def create_user(self, u: User) -> User:
        u.id = self._assign("user")
        self._users[u.id] = u
        return u
    def get_user(self, uid: int): return self._users.get(uid)
    def list_users(self): return list(self._users.values())
    def update_user(self, u: User): self._users[u.id] = u
    def delete_user(self, uid: int): self._users.pop(uid, None)

    # Studios
    def create_studio(self, s: Studio) -> Studio:
        s.id = self._assign("studio"); self._studios[s.id]=s; return s
    def get_studio(self, sid:int): return self._studios.get(sid)
    def list_studios(self): return list(self._studios.values())
    def update_studio(self,s:Studio): self._studios[s.id]=s
    def delete_studio(self,sid:int): self._studios.pop(sid,None)

    # Tags
    def create_tag(self,t:Tag): t.id=self._assign("tag"); self._tags[t.id]=t; return t
    def get_tag(self,tid:int): return self._tags.get(tid)
    def list_tags(self): return list(self._tags.values())
    def update_tag(self,t:Tag): self._tags[t.id]=t
    def delete_tag(self,tid:int):
        self._tags.pop(tid,None)
        for k,v in list(self._anime_tags.items()):
            if tid in v:
                v.remove(tid)

    # Animes
    def create_anime(self,a:Anime): a.id=self._assign("anime"); self._animes[a.id]=a; return a
    def get_anime(self,aid:int): return self._animes.get(aid)

    def list_animes(self, q=None, order_by="title", tag_id: Optional[int]=None, studio_id: Optional[int]=None):
        res = list(self._animes.values())
        if q:
            ql = q.lower()
            res = [r for r in res if ql in r.title.lower()]
        if tag_id is not None:
            res = [r for r in res if tag_id in self._anime_tags.get(r.id, [])]
        if studio_id is not None:
            res = [r for r in res if r.studio_id == studio_id]
        # safe ordering
        if order_by == "total_episodes":
            res.sort(key=lambda x: (x.total_episodes is None, x.total_episodes))
        elif order_by == "id":
            res.sort(key=lambda x: x.id)
        else:
            res.sort(key=lambda x: (x.title or "").lower())
        return res


    def update_anime(self,a:Anime): self._animes[a.id]=a
    def delete_anime(self,aid:int):
        self._animes.pop(aid,None)
        self._anime_tags.pop(aid,None)
        for wid, w in list(self._watches.items()):
            if w.anime_id == aid: self._watches.pop(wid, None)

    def set_anime_tags(self, anime_id:int, tag_ids:List[int]):
        self._anime_tags[anime_id] = tag_ids[:]
    def get_anime_tags(self, anime_id:int):
        return [self._tags[tid] for tid in self._anime_tags.get(anime_id, []) if tid in self._tags]

    # Watches
    def create_watch(self,w:WatchEntry): w.id=self._assign("watch"); self._watches[w.id]=w; return w
    def get_watch(self,wid:int): return self._watches.get(wid)

    def list_watches_for_user(self, user_id: int, status: Optional[str] = None, min_score: Optional[int] = None, order_by: str = "updated_at"):
        res = [w for w in self._watches.values() if w.user_id == user_id]
        if status:
            res = [w for w in res if w.status == status]
        if min_score is not None:
            res = [w for w in res if (w.score is not None and w.score >= min_score)]
        if order_by == "score":
            res.sort(key=lambda x: (x.score if x.score is not None else -1), reverse=True)
        elif order_by == "episodes_watched":
            res.sort(key=lambda x: x.episodes_watched, reverse=True)
        else:
            res.sort(key=lambda x: x.updated_at, reverse=True)
        return res

    def update_watch(self,w:WatchEntry): self._watches[w.id]=w
    def delete_watch(self,wid:int): self._watches.pop(wid,None)

