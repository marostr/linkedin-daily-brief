Generate LinkedIn daily briefing:

1. Query unprocessed posts:
source ~/.linkedin-feed/cookies.env && python3 ~/linkedin-daily-brief/linkedin_feed.py unprocessed

2. Filter by priority keywords: ruby, rails, ai, llm, agent, claude, founder, startup, learning, education, hotwire, mcp, anthropic, openai, gpt

3. Generate briefing with:
   - Must-Read (top 5-10 posts)
   - Action Queue (engagement suggestions with draft comments)
   - Content Opportunities

4. MUST include direct LinkedIn post URLs for each item

5. Save to ~/.openclaw/workspace/linkedin/briefings/YYYY-MM-DD.md

6. Deliver briefing summary to Marcin

7. Mark all as processed:
source ~/.linkedin-feed/cookies.env && python3 ~/linkedin-daily-brief/linkedin_feed.py mark-processed --all
