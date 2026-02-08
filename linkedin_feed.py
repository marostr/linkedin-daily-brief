"""Fetch LinkedIn feed posts and store them in a local SQLite database."""

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

from linkedin_api import Linkedin
from requests.cookies import RequestsCookieJar

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "linkedin_feed.db")


def init_db(db_path=DEFAULT_DB_PATH):
    """Create the posts table if it doesn't exist."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            url TEXT PRIMARY KEY,
            author_name TEXT,
            author_profile TEXT,
            content TEXT,
            old TEXT,
            fetched_at TEXT NOT NULL,
            processed INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def store_posts(db_path, posts):
    """Insert new posts into the database. Returns count of newly inserted posts."""
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0

    for p in posts:
        url = p.get("url")
        if not url:
            continue
        try:
            conn.execute(
                "INSERT INTO posts (url, author_name, author_profile, content, old, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (url, p.get("author_name", ""), p.get("author_profile", ""),
                 p.get("content", ""), p.get("old", ""), now),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()
    return inserted


def get_unprocessed(db_path=DEFAULT_DB_PATH):
    """Return all unprocessed posts as a list of dicts."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT url, author_name, author_profile, content, old, fetched_at "
        "FROM posts WHERE processed = 0 ORDER BY rowid"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def mark_processed(db_path, urls):
    """Mark posts as processed by their URLs."""
    conn = sqlite3.connect(db_path)
    conn.executemany(
        "UPDATE posts SET processed = 1 WHERE url = ?",
        [(url,) for url in urls],
    )
    conn.commit()
    conn.close()


def fetch_feed(jsessionid, li_at, limit=200):
    """Authenticate via cookies and return feed posts."""
    jar = RequestsCookieJar()
    jar.set("JSESSIONID", f'"{jsessionid}"', domain=".linkedin.com")
    jar.set("li_at", li_at, domain=".linkedin.com")

    api = Linkedin("", "", cookies=jar)
    return api.get_feed_posts(limit=limit)


def main():
    jsessionid = os.environ.get("LINKEDIN_JSESSIONID")
    li_at = os.environ.get("LINKEDIN_LI_AT")

    if not jsessionid or not li_at:
        print(
            "Set LINKEDIN_JSESSIONID and LINKEDIN_LI_AT environment variables.",
            file=sys.stderr,
        )
        sys.exit(1)

    db_path = os.environ.get("LINKEDIN_DB_PATH", DEFAULT_DB_PATH)
    init_db(db_path)

    posts = fetch_feed(jsessionid, li_at)
    new_count = store_posts(db_path, posts)
    unprocessed = get_unprocessed(db_path)

    print(json.dumps(unprocessed, indent=2, ensure_ascii=False))
    print(
        f"\n--- {new_count} new / {len(unprocessed)} unprocessed / {len(posts)} fetched ---",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
