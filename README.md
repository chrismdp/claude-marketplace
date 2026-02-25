# Chris Parsons' Claude Code Plugin Marketplace

A curated collection of Claude Code plugins.

## Installation

```bash
claude plugins marketplace add chrismdp github chrismdp/claude-marketplace
```

Then install individual plugins:

```bash
claude plugins install lockbox@chrismdp
```

## Available Plugins

| Plugin | Category | Description |
|--------|----------|-------------|
| [lockbox](https://github.com/chrismdp/lockbox) | Security | Taint-aware context quarantine — blocks external actions when untrusted data enters the session |

## Adding a Plugin

Open a PR adding your plugin entry to `.claude-plugin/marketplace.json` with:

- `name` — kebab-case plugin name
- `description` — what it does in one sentence
- `category` — one of: development, productivity, testing, database, design, deployment, monitoring, security, learning
- `source` — git URL to your plugin repo
- `tags` — relevant keywords

## Author

[Chris Parsons](https://chrismdp.com) — AI training and consulting
