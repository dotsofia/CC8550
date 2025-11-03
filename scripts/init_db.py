# scripts/init_db.py
import sqlite3
import os

DB = os.path.join("data","anime.db")
os.makedirs(os.path.dirname(DB), exist_ok=True)
with sqlite3.connect(DB) as c:
    cur = c.cursor()
    cur.executescript("""
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
    """)
    print("initialized db at", DB)

