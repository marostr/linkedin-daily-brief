# LinkedIn Briefing Prompt Design

## Decision

Replace the generic keyword-filter briefing prompt with one built around Marcin's five content identity angles. The LLM does all scoring and filtering — no Python code needed.

## Five Content Angles

1. **Ruby on AI** (rubyonai.com) — Ruby/Rails + AI/LLM intersection, agentic coding, AI agents, AI-assisted coding
2. **Education & community** (nerds.family) — learning, teaching, mentorship
3. **CTO/founder** — scaling, leadership, hiring, startup experience
4. **Ruby/Rails practitioner** — daily craft (Hotwire, Turbo, Stimulus, Sidekiq, Kamal)
5. **Claude Code & AI tooling** — MCP, Anthropic ecosystem, developer AI tools

## Scoring Approach

Qualitative, not numeric. The LLM judges relevance based on:
- Multi-angle matches score highest (Ruby on AI is the top niche)
- Engagement potential: questions, opinions, stories > announcements
- Core question: "Can Marcin do something with this post?"

## Output

Markdown file at `~/.openclaw/workspace/linkedin/briefings/YYYY-MM-DD.md` with three sections:
- Must-Read (top 5-10, tagged by angle)
- Action Queue (posts to engage with, draft comments, direct URLs)
- Content Opportunities (content ideas mapped to platform)

## Future Improvements

- Add voice/tone examples for draft comments
- Add sample output entries to reduce ambiguity
- Iterate based on actual briefing quality
