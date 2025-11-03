# app/models.py
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class User:
    id: Optional[int]
    username: str
    created_at: str = now_iso()

@dataclass
class Studio:
    id: Optional[int]
    name: str
    created_at: str = now_iso()

@dataclass
class Tag:
    id: Optional[int]
    name: str

@dataclass
class Anime:
    id: Optional[int]
    title: str
    total_episodes: Optional[int] = None  # None -> unknown / ongoing
    studio_id: Optional[int] = None

@dataclass
class WatchEntry:
    id: Optional[int]
    user_id: int
    anime_id: int
    episodes_watched: int
    score: Optional[int] = None  # 0-10
    status: str = "plan_to_watch"  # "watching", "completed", "plan_to_watch", "dropped"
    updated_at: str = now_iso()

