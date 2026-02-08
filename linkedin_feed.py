"""Fetch LinkedIn feed posts and store them in a local SQLite database."""

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

from linkedin_api import Linkedin
from requests.cookies import RequestsCookieJar

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "linkedin_feed.db")
BATCH_SIZE = 50
DEFAULT_LIMIT = 200


def estimate_posted_at(old_text, fetched_at):
    """Convert a relative age string like '2h' into an absolute datetime.

    Returns None if the string can't be parsed.
    """
    if not old_text or old_text == "None":
        return None

    time_part = old_text.split("•")[0].strip()

    match = re.match(r"(\d+)\s*(mo|min|mi|yr|hr|s|m|h|d|w)", time_part, re.IGNORECASE)
    if not match:
        if "now" in time_part.lower() or "just" in time_part.lower():
            return fetched_at
        return None

    value = int(match.group(1))
    unit = match.group(2).lower()

    if unit == "s":
        delta = timedelta(seconds=value)
    elif unit in ("m", "mi", "min"):
        delta = timedelta(minutes=value)
    elif unit in ("h", "hr"):
        delta = timedelta(hours=value)
    elif unit == "d":
        delta = timedelta(days=value)
    elif unit == "w":
        delta = timedelta(weeks=value)
    elif unit == "mo":
        delta = timedelta(days=value * 30)
    elif unit == "yr":
        delta = timedelta(days=value * 365)
    else:
        return None

    return fetched_at - delta


def init_db(db_path=DEFAULT_DB_PATH):
    """Create the posts table if it doesn't exist."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            url TEXT PRIMARY KEY,
            author_name TEXT,
            author_profile TEXT,
            content TEXT,
            posted_at TEXT,
            fetched_at TEXT NOT NULL,
            processed INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fetches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            fetched INTEGER NOT NULL,
            inserted INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def store_posts(db_path, posts):
    """Insert new posts into the database. Returns count of newly inserted posts."""
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    inserted = 0

    for p in posts:
        url = p.get("url")
        if not url:
            continue

        posted_at = estimate_posted_at(p.get("old", ""), now)
        posted_at_iso = posted_at.isoformat() if posted_at else None

        try:
            conn.execute(
                "INSERT INTO posts (url, author_name, author_profile, content, posted_at, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (url, p.get("author_name", ""), p.get("author_profile", ""),
                 p.get("content", ""), posted_at_iso, now_iso),
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
        "SELECT url, author_name, author_profile, content, posted_at, fetched_at "
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


def log_fetch(db_path, fetched, inserted):
    """Record a fetch operation in the audit log."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO fetches (started_at, fetched, inserted) VALUES (?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), fetched, inserted),
    )
    conn.commit()
    conn.close()


def get_fetch_log(db_path=DEFAULT_DB_PATH):
    """Return the fetch audit log, most recent first."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT started_at, fetched, inserted FROM fetches ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def fetch_feed_batched(get_feed_posts_fn, limit=DEFAULT_LIMIT):
    """Fetch feed posts in batches of BATCH_SIZE.

    Accepts a callable (e.g. api.get_feed_posts) to allow testing
    without hitting the real API. Stops when the API returns zero posts.
    """
    all_posts = []
    offset = 0

    while len(all_posts) < limit:
        batch = get_feed_posts_fn(limit=BATCH_SIZE, offset=offset)
        if not batch:
            break
        all_posts.extend(batch)
        offset += BATCH_SIZE

    return all_posts[:limit]


def fetch_feed(jsessionid, li_at, limit=DEFAULT_LIMIT):
    """Authenticate via cookies and return feed posts in batches."""
    jar = RequestsCookieJar()
    jar.set("JSESSIONID", f'"{jsessionid}"', domain=".linkedin.com")
    jar.set("li_at", li_at, domain=".linkedin.com")

    api = Linkedin("", "", cookies=jar)
    return fetch_feed_batched(api.get_feed_posts, limit=limit)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fetch LinkedIn feed posts")
    parser.add_argument(
        "limit", nargs="?", type=int, default=DEFAULT_LIMIT,
        help=f"Number of posts to fetch (default: {DEFAULT_LIMIT})",
    )
    args = parser.parse_args()

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

    posts = fetch_feed(jsessionid, li_at, limit=args.limit)
    new_count = store_posts(db_path, posts)
    log_fetch(db_path, fetched=len(posts), inserted=new_count)
    unprocessed = get_unprocessed(db_path)

    print(f"Fetched:      {len(posts)}")
    print(f"New:          {new_count}")
    print(f"Unprocessed:  {len(unprocessed)}")


if __name__ == "__main__":
    main()
