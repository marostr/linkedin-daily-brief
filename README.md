# LinkedIn Feed Scraper

Fetches posts from your LinkedIn feed and stores them in a local SQLite database for later processing.

## Setup

```bash
pip install -r requirements.txt
```

Set environment variables with your LinkedIn session cookies:

```bash
export LINKEDIN_JSESSIONID="your-jsessionid"
export LINKEDIN_LI_AT="your-li-at-token"
```

You can find these in your browser's dev tools under Application > Cookies > linkedin.com.

Optionally set a custom database path (defaults to `linkedin_feed.db` in the script directory):

```bash
export LINKEDIN_DB_PATH="/path/to/your.db"
```

## Usage

### Fetch posts

```bash
python linkedin_feed.py fetch         # fetch 200 posts (default)
python linkedin_feed.py fetch 100     # fetch 100 posts
```

Fetches posts in batches of 50, stores new ones in the database, and prints statistics:

```
Fetched:      200
New:          47
Unprocessed:  183
```

### View unprocessed posts

```bash
python linkedin_feed.py unprocessed
```

Outputs all unprocessed posts as JSON.

### Mark posts as processed

```bash
python linkedin_feed.py mark-processed <url1> <url2> ...   # mark specific posts
python linkedin_feed.py mark-processed --all                # mark all unprocessed
```

## Database schema

**posts** — one row per unique feed post:
- `url` (PK), `author_name`, `author_profile`, `content`, `posted_at`, `fetched_at`, `processed`

**fetches** — audit log of each fetch run:
- `id`, `started_at`, `fetched`, `inserted`

## Testing

```bash
pytest test_linkedin_feed.py -v
```
