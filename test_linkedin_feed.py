import sqlite3
from linkedin_feed import init_db, store_posts, get_unprocessed, mark_processed


class TestInitDb:
    def test_creates_posts_table(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        conn = sqlite3.connect(db)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor]
        conn.close()
        assert "posts" in tables


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
