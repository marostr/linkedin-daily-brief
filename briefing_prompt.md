Generate a LinkedIn daily briefing for Marcin.

## Who Marcin is

Score every post against these five content angles:

- **Ruby on AI** — runs rubyonai.com, focused on the intersection of Ruby/Rails and AI/LLM, especially agentic coding, AI agents, and AI-assisted coding
- **Education & community** — building nerds.family, interested in learning, teaching, mentorship, community building, bootcamps
- **CTO/founder** — technical founder and CTO, experienced with scaling, leadership, hiring, fundraising, startup life
- **Ruby/Rails practitioner** — daily craft: Ruby, Rails, Hotwire, Stimulus, Turbo, Sidekiq, Kamal
- **Claude Code & AI tooling** — active Claude Code user and builder, MCP, Anthropic ecosystem, AI agents, developer tooling

## Scoring

- Posts matching multiple angles score highest — especially Ruby on AI (it's his niche)
- Posts inviting engagement score higher: questions, opinions, hot takes, stories, lessons learned
- Posts that are pure announcements or self-promotion score lower
- A post is valuable when Marcin can *do something with it*: reply with substance, repost with his take, or use it as content inspiration
- Exclude posts matching zero angles

## Steps

1. Fetch unprocessed posts:
   `source ~/.linkedin-feed/cookies.env && python3 ~/linkedin-daily-brief/linkedin_feed.py unprocessed`

2. Score and filter posts using the criteria above

3. Generate the briefing (format below) and save to:
   `~/.openclaw/workspace/linkedin/briefings/YYYY-MM-DD.md`

4. Deliver the briefing summary

5. Mark all posts as processed:
   `source ~/.linkedin-feed/cookies.env && python3 ~/linkedin-daily-brief/linkedin_feed.py mark-processed --all`

## Output format

### Must-Read (top 5-10)

Sorted by score. Each entry:
- Author name
- One-line summary
- Matching angles as tags (e.g., `[ruby-on-ai]` `[cto-founder]`)
- Why it's relevant to Marcin specifically
- Direct LinkedIn post URL

### Action Queue

Posts where Marcin should engage. Each entry:
- **Direct LinkedIn post URL** (clickable link to the exact post)
- Which angle it connects to
- Draft comment in Marcin's voice — substantive, adds perspective or experience, not "Great post!"

### Content Opportunities

Posts that spark ideas for Marcin's own content. Each entry:
- Source post URL
- Target platform: rubyonai.com, nerds.family, or LinkedIn original post
- One-line content idea

A post can appear in multiple sections.
