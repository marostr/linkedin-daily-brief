import json
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from linkedin_feed import (
    init_db, store_posts, get_unprocessed, mark_processed, estimate_posted_at,
    log_fetch, get_fetch_log, fetch_feed, fetch_feed_batched, get_posts,
    main, BATCH_SIZE, DEFAULT_LIMIT,
)


class TestEstimatePostedAt:
    def test_minutes(self):
        now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
        result = estimate_posted_at("14m", now)
        assert result == datetime(2026, 2, 8, 11, 46, 0, tzinfo=timezone.utc)

    def test_hours(self):
        now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
        result = estimate_posted_at("3h", now)
        assert result == datetime(2026, 2, 8, 9, 0, 0, tzinfo=timezone.utc)

    def test_days(self):
        now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
        result = estimate_posted_at("2d", now)
        assert result == datetime(2026, 2, 6, 12, 0, 0, tzinfo=timezone.utc)

    def test_weeks(self):
        now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
        result = estimate_posted_at("1w", now)
        assert result == datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_months(self):
        now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
        result = estimate_posted_at("2 mo", now)
        # 2 * 30 = 60 days back from Feb 8 = Dec 10 (approximate)
        assert result == datetime(2025, 12, 10, 12, 0, 0, tzinfo=timezone.utc)

    def test_strips_suffixes(self):
        now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
        result = estimate_posted_at("5h • Edited • 2nd", now)
        assert result == datetime(2026, 2, 8, 7, 0, 0, tzinfo=timezone.utc)

    def test_just_now_returns_fetched_at(self):
        now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
        result = estimate_posted_at("Just now", now)
        assert result == now

    def test_unparseable_returns_none(self):
        now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
        assert estimate_posted_at("", now) is None
        assert estimate_posted_at(None, now) is None
        assert estimate_posted_at("None", now) is None

    def test_seconds(self):
        now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
        result = estimate_posted_at("30s", now)
        assert result == datetime(2026, 2, 8, 11, 59, 30, tzinfo=timezone.utc)


class TestInitDb:
    def test_creates_posts_table(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        conn = sqlite3.connect(db)
        cursor = conn.execute("PRAGMA table_info(posts)")
        columns = [row[1] for row in cursor]
        conn.close()
        assert "posted_at" in columns
        assert "old" not in columns


class TestStorePosts:
    def test_stores_new_posts(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        posts = [
            {"url": "https://linkedin.com/feed/update/urn:li:activity:1",
             "author_name": "Alice", "author_profile": "https://linkedin.com/in/alice",
             "content": "Hello world", "old": "2h"},
        ]
        count = store_posts(db, posts)
        assert count == 1

    def test_computes_posted_at_from_old(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        posts = [
            {"url": "https://linkedin.com/feed/update/urn:li:activity:1",
             "author_name": "Alice", "author_profile": "", "content": "A", "old": "2h"},
        ]
        store_posts(db, posts)
        result = get_unprocessed(db)
        # posted_at should be an ISO timestamp, roughly 2h before now
        posted_at = datetime.fromisoformat(result[0]["posted_at"])
        age = datetime.now(timezone.utc) - posted_at
        assert timedelta(hours=1, minutes=50) < age < timedelta(hours=2, minutes=10)

    def test_skips_duplicate_urls(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        posts = [
            {"url": "https://linkedin.com/feed/update/urn:li:activity:1",
             "author_name": "Alice", "author_profile": "", "content": "First", "old": "2h"},
        ]
        store_posts(db, posts)
        count = store_posts(db, posts)
        assert count == 0

    def test_skips_posts_without_url(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        posts = [{"author_name": "NoURL", "content": "No link"}]
        count = store_posts(db, posts)
        assert count == 0

    def test_returns_count_of_new_posts(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        posts = [
            {"url": "https://linkedin.com/feed/update/urn:li:activity:1",
             "author_name": "Alice", "author_profile": "", "content": "A", "old": "1h"},
            {"url": "https://linkedin.com/feed/update/urn:li:activity:2",
             "author_name": "Bob", "author_profile": "", "content": "B", "old": "3h"},
            {"url": "https://linkedin.com/feed/update/urn:li:activity:3",
             "author_name": "Carol", "author_profile": "", "content": "C", "old": "5h"},
        ]
        store_posts(db, posts[:2])
        count = store_posts(db, posts)
        assert count == 1


class TestGetUnprocessed:
    def test_returns_unprocessed_posts(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        posts = [
            {"url": "https://linkedin.com/feed/update/urn:li:activity:1",
             "author_name": "Alice", "author_profile": "", "content": "Hello", "old": "2h"},
            {"url": "https://linkedin.com/feed/update/urn:li:activity:2",
             "author_name": "Bob", "author_profile": "", "content": "World", "old": "3h"},
        ]
        store_posts(db, posts)
        unprocessed = get_unprocessed(db)
        assert len(unprocessed) == 2
        assert unprocessed[0]["author_name"] == "Alice"

    def test_excludes_processed_posts(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        posts = [
            {"url": "https://linkedin.com/feed/update/urn:li:activity:1",
             "author_name": "Alice", "author_profile": "", "content": "A", "old": "1h"},
            {"url": "https://linkedin.com/feed/update/urn:li:activity:2",
             "author_name": "Bob", "author_profile": "", "content": "B", "old": "2h"},
        ]
        store_posts(db, posts)
        mark_processed(db, ["https://linkedin.com/feed/update/urn:li:activity:1"])
        unprocessed = get_unprocessed(db)
        assert len(unprocessed) == 1
        assert unprocessed[0]["author_name"] == "Bob"

    def test_returns_empty_list_when_all_processed(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        posts = [
            {"url": "https://linkedin.com/feed/update/urn:li:activity:1",
             "author_name": "Alice", "author_profile": "", "content": "A", "old": "1h"},
        ]
        store_posts(db, posts)
        mark_processed(db, ["https://linkedin.com/feed/update/urn:li:activity:1"])
        assert get_unprocessed(db) == []


def _seed_dated_posts(db):
    """Insert posts with known posted_at timestamps for date filtering tests."""
    conn = sqlite3.connect(db)
    now_iso = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    posts = [
        ("https://linkedin.com/post/1", "Alice", "", "Old post",
         datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc).isoformat(), now_iso, 0),
        ("https://linkedin.com/post/2", "Bob", "", "Mid post",
         datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc).isoformat(), now_iso, 1),
        ("https://linkedin.com/post/3", "Carol", "", "Recent post",
         datetime(2026, 2, 1, 10, 0, 0, tzinfo=timezone.utc).isoformat(), now_iso, 0),
        ("https://linkedin.com/post/4", "Dave", "", "No date",
         None, now_iso, 0),
    ]
    conn.executemany(
        "INSERT INTO posts (url, author_name, author_profile, content, posted_at, fetched_at, processed) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)", posts,
    )
    conn.commit()
    conn.close()


class TestGetPosts:
    def test_no_filters_returns_all_posts_with_dates(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        _seed_dated_posts(db)
        posts = get_posts(db)
        # posts without posted_at are excluded
        assert len(posts) == 3
        urls = [p["url"] for p in posts]
        assert "https://linkedin.com/post/4" not in urls

    def test_after_filters_posts(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        _seed_dated_posts(db)
        after = datetime(2026, 1, 10, 0, 0, 0, tzinfo=timezone.utc)
        posts = get_posts(db, after=after)
        assert len(posts) == 2
        urls = [p["url"] for p in posts]
        assert "https://linkedin.com/post/2" in urls
        assert "https://linkedin.com/post/3" in urls

    def test_before_filters_posts(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        _seed_dated_posts(db)
        before = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        posts = get_posts(db, before=before)
        assert len(posts) == 2
        urls = [p["url"] for p in posts]
        assert "https://linkedin.com/post/1" in urls
        assert "https://linkedin.com/post/2" in urls

    def test_after_and_before_combined(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        _seed_dated_posts(db)
        after = datetime(2026, 1, 10, 0, 0, 0, tzinfo=timezone.utc)
        before = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        posts = get_posts(db, after=after, before=before)
        assert len(posts) == 1
        assert posts[0]["url"] == "https://linkedin.com/post/2"

    def test_includes_both_processed_and_unprocessed(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        _seed_dated_posts(db)
        posts = get_posts(db)
        processed_flags = {p["url"]: p["processed"] for p in posts}
        assert processed_flags["https://linkedin.com/post/2"] == 1
        assert processed_flags["https://linkedin.com/post/1"] == 0

    def test_returns_empty_when_no_matches(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        _seed_dated_posts(db)
        after = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
        posts = get_posts(db, after=after)
        assert posts == []

    def test_ordered_by_posted_at(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        _seed_dated_posts(db)
        posts = get_posts(db)
        dates = [p["posted_at"] for p in posts]
        assert dates == sorted(dates)


class TestMarkProcessed:
    def test_marks_posts_as_processed(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        posts = [
            {"url": "https://linkedin.com/feed/update/urn:li:activity:1",
             "author_name": "Alice", "author_profile": "", "content": "A", "old": "1h"},
        ]
        store_posts(db, posts)
        mark_processed(db, ["https://linkedin.com/feed/update/urn:li:activity:1"])

        conn = sqlite3.connect(db)
        row = conn.execute("SELECT processed FROM posts WHERE url = ?",
                           ("https://linkedin.com/feed/update/urn:li:activity:1",)).fetchone()
        conn.close()
        assert row[0] == 1

    def test_ignores_unknown_urls(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        mark_processed(db, ["https://linkedin.com/feed/update/urn:li:activity:999"])
        # no error raised


class TestFetchAudit:
    def test_logs_a_fetch(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        log_fetch(db, fetched=150, inserted=42)
        log = get_fetch_log(db)
        assert len(log) == 1
        assert log[0]["fetched"] == 150
        assert log[0]["inserted"] == 42
        assert log[0]["started_at"] is not None

    def test_logs_multiple_fetches_in_order(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        log_fetch(db, fetched=100, inserted=100)
        log_fetch(db, fetched=100, inserted=20)
        log = get_fetch_log(db)
        assert len(log) == 2
        # most recent first
        assert log[0]["inserted"] == 20
        assert log[1]["inserted"] == 100

    def test_init_db_creates_fetches_table(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        conn = sqlite3.connect(db)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert "fetches" in tables


class TestFetchFeedBatched:
    def test_batch_size_is_50(self):
        assert BATCH_SIZE == 50

    def test_default_limit_is_200(self):
        assert DEFAULT_LIMIT == 200

    def test_calls_api_in_batches(self):
        calls = []

        def fake_get_feed_posts(limit, offset, exclude_promoted_posts=True):
            calls.append({"limit": limit, "offset": offset})
            return [{"url": f"https://linkedin.com/feed/update/urn:li:activity:{offset + i}",
                      "author_name": f"Author{offset + i}", "author_profile": "",
                      "content": f"Post {offset + i}", "old": "1h"}
                     for i in range(limit)]

        posts = fetch_feed_batched(fake_get_feed_posts, limit=150)
        assert len(calls) == 3  # 50 + 50 + 50
        assert all(c["limit"] == 50 for c in calls)
        assert [c["offset"] for c in calls] == [0, 50, 100]
        assert len(posts) == 150

    def test_keeps_fetching_when_batch_is_partial(self):
        calls = []

        def fake_get_feed_posts(limit, offset, exclude_promoted_posts=True):
            calls.append({"limit": limit, "offset": offset})
            if offset == 50:
                # partial batch (e.g. promoted posts filtered out)
                return [{"url": "https://linkedin.com/feed/update/urn:li:activity:99",
                          "author_name": "Last", "author_profile": "",
                          "content": "Last post", "old": "1d"}]
            if offset == 100:
                return []  # truly exhausted
            return [{"url": f"https://linkedin.com/feed/update/urn:li:activity:{offset + i}",
                      "author_name": f"A{offset + i}", "author_profile": "",
                      "content": f"P{offset + i}", "old": "1h"}
                     for i in range(limit)]

        posts = fetch_feed_batched(fake_get_feed_posts, limit=200)
        assert len(calls) == 3  # kept going past partial batch
        assert len(posts) == 51

    def test_stops_when_api_returns_empty(self):
        calls = []

        def fake_get_feed_posts(limit, offset, exclude_promoted_posts=True):
            calls.append({"limit": limit, "offset": offset})
            if offset >= 50:
                return []
            return [{"url": f"https://linkedin.com/feed/update/urn:li:activity:{offset + i}",
                      "author_name": f"A{offset + i}", "author_profile": "",
                      "content": f"P{offset + i}", "old": "1h"}
                     for i in range(limit)]

        posts = fetch_feed_batched(fake_get_feed_posts, limit=200)
        assert len(calls) == 2
        assert len(posts) == 50

    def test_retries_once_on_failure_then_succeeds(self):
        calls = []
        fail_once = [True]

        def fake_get_feed_posts(limit, offset, exclude_promoted_posts=True):
            calls.append({"limit": limit, "offset": offset})
            if offset == 0 and fail_once[0]:
                fail_once[0] = False
                raise ConnectionError("network blip")
            return [{"url": f"https://linkedin.com/feed/update/urn:li:activity:{offset + i}",
                      "author_name": f"A{offset + i}", "author_profile": "",
                      "content": f"P{offset + i}", "old": "1h"}
                     for i in range(limit)]

        posts = fetch_feed_batched(fake_get_feed_posts, limit=50, retry_delay=0)
        assert len(posts) == 50
        # first call failed, retry succeeded
        assert len(calls) == 2
        assert calls[0]["offset"] == 0
        assert calls[1]["offset"] == 0

    def test_returns_partial_results_on_persistent_failure(self, capsys):
        calls = []

        def fake_get_feed_posts(limit, offset, exclude_promoted_posts=True):
            calls.append({"limit": limit, "offset": offset})
            if offset >= 50:
                raise ConnectionError("server down")
            return [{"url": f"https://linkedin.com/feed/update/urn:li:activity:{offset + i}",
                      "author_name": f"A{offset + i}", "author_profile": "",
                      "content": f"P{offset + i}", "old": "1h"}
                     for i in range(limit)]

        posts = fetch_feed_batched(fake_get_feed_posts, limit=200, retry_delay=0)
        assert len(posts) == 50  # first batch succeeded, second failed
        err = capsys.readouterr().err
        assert "server down" in err


class TestFetchFeedCookies:
    def test_strips_existing_quotes_from_jsessionid(self, monkeypatch):
        """JSESSIONID must be wrapped in exactly one layer of quotes."""
        captured = {}

        def fake_init(self, email, password, cookies=None):
            captured["cookies"] = cookies

        monkeypatch.setattr("linkedin_feed.Linkedin.__init__", fake_init)

        monkeypatch.setattr("linkedin_feed.fetch_feed_batched", lambda fn, limit: [])

        # Value already has quotes (as it would from a .env file)
        fetch_feed('"ajax:123456"', "some-li-at", limit=1)
        jsessionid_val = captured["cookies"]["JSESSIONID"]
        assert jsessionid_val == '"ajax:123456"'
        assert '""' not in jsessionid_val

    def test_adds_quotes_when_missing(self, monkeypatch):
        captured = {}

        def fake_init(self, email, password, cookies=None):
            captured["cookies"] = cookies

        monkeypatch.setattr("linkedin_feed.Linkedin.__init__", fake_init)

        monkeypatch.setattr("linkedin_feed.fetch_feed_batched", lambda fn, limit: [])

        fetch_feed("ajax:123456", "some-li-at", limit=1)
        jsessionid_val = captured["cookies"]["JSESSIONID"]
        assert jsessionid_val == '"ajax:123456"'


def _seed_posts(db, count=3):
    """Insert test posts and return their URLs."""
    posts = [
        {"url": f"https://linkedin.com/feed/update/urn:li:activity:{i}",
         "author_name": f"Author{i}", "author_profile": "", "content": f"Post {i}", "old": "1h"}
        for i in range(count)
    ]
    store_posts(db, posts)
    return [p["url"] for p in posts]


class TestMarkProcessedCLI:
    def test_marks_specific_urls(self, tmp_path, monkeypatch, capsys):
        db = str(tmp_path / "test.db")
        init_db(db)
        urls = _seed_posts(db)

        monkeypatch.setenv("LINKEDIN_DB_PATH", db)
        monkeypatch.setattr(sys, "argv", [
            "linkedin_feed.py", "mark-processed", urls[0], urls[1],
        ])
        main()

        out = capsys.readouterr().out
        assert "Marked 2" in out

        unprocessed = get_unprocessed(db)
        assert len(unprocessed) == 1
        assert unprocessed[0]["url"] == urls[2]

    def test_marks_all_unprocessed(self, tmp_path, monkeypatch, capsys):
        db = str(tmp_path / "test.db")
        init_db(db)
        _seed_posts(db)

        monkeypatch.setenv("LINKEDIN_DB_PATH", db)
        monkeypatch.setattr(sys, "argv", [
            "linkedin_feed.py", "mark-processed", "--all",
        ])
        main()

        out = capsys.readouterr().out
        assert "Marked 3" in out
        assert get_unprocessed(db) == []

    def test_all_flag_with_no_unprocessed(self, tmp_path, monkeypatch, capsys):
        db = str(tmp_path / "test.db")
        init_db(db)

        monkeypatch.setenv("LINKEDIN_DB_PATH", db)
        monkeypatch.setattr(sys, "argv", [
            "linkedin_feed.py", "mark-processed", "--all",
        ])
        main()

        out = capsys.readouterr().out
        assert "Marked 0" in out


class TestPostsCLI:
    def test_no_filters_outputs_json(self, tmp_path, monkeypatch, capsys):
        db = str(tmp_path / "test.db")
        init_db(db)
        _seed_dated_posts(db)

        monkeypatch.setenv("LINKEDIN_DB_PATH", db)
        monkeypatch.setattr(sys, "argv", ["linkedin_feed.py", "posts"])
        main()

        out = capsys.readouterr().out
        posts = json.loads(out)
        assert len(posts) == 3

    def test_after_flag(self, tmp_path, monkeypatch, capsys):
        db = str(tmp_path / "test.db")
        init_db(db)
        _seed_dated_posts(db)

        monkeypatch.setenv("LINKEDIN_DB_PATH", db)
        monkeypatch.setattr(sys, "argv", [
            "linkedin_feed.py", "posts", "--after", "2026-01-10",
        ])
        main()

        out = capsys.readouterr().out
        posts = json.loads(out)
        assert len(posts) == 2

    def test_before_flag(self, tmp_path, monkeypatch, capsys):
        db = str(tmp_path / "test.db")
        init_db(db)
        _seed_dated_posts(db)

        monkeypatch.setenv("LINKEDIN_DB_PATH", db)
        monkeypatch.setattr(sys, "argv", [
            "linkedin_feed.py", "posts", "--before", "2026-01-20",
        ])
        main()

        out = capsys.readouterr().out
        posts = json.loads(out)
        assert len(posts) == 2

    def test_both_flags(self, tmp_path, monkeypatch, capsys):
        db = str(tmp_path / "test.db")
        init_db(db)
        _seed_dated_posts(db)

        monkeypatch.setenv("LINKEDIN_DB_PATH", db)
        monkeypatch.setattr(sys, "argv", [
            "linkedin_feed.py", "posts", "--after", "2026-01-10", "--before", "2026-01-20",
        ])
        main()

        out = capsys.readouterr().out
        posts = json.loads(out)
        assert len(posts) == 1
        assert posts[0]["url"] == "https://linkedin.com/post/2"
