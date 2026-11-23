# Chris Parsons' Claude Code Plugin Marketplace

A curated collection of Claude Code plugins.

## Available Plugins

| Plugin | Category | Description |
|--------|----------|-------------|
| [chrismdp](#chrismdp) | Productivity | Five public skills by Chris Parsons |

### chrismdp

- `capture` saves individual thoughts as Zettelkasten notes in Obsidian.
- `delegate` assigns scoped coding tasks to workers and coordinates review and integration.
- `dream` finds patterns, tensions and open questions across recent notes and saved articles.
- `lateral` gives each agent a random dictionary word to bring a different perspective to a question.
- `ralph` picks the next ticket in a queue, completes it, checks the result and marks it done.

Run these commands in a Claude Code session.

```text
/plugin marketplace add chrismdp/claude-marketplace
/plugin install chrismdp@chrismdp
```

## Adding a Plugin

Open a PR adding your plugin entry to `.claude-plugin/marketplace.json` with:

- `name` — kebab-case plugin name
- `description` — what it does in one sentence
- `category` — one of: development, productivity, testing, database, design, deployment, monitoring, security, learning
- `source` — git URL to your plugin repo
- `tags` — relevant keywords

## Author

[Chris Parsons](https://chrismdp.com) — AI training and consulting
