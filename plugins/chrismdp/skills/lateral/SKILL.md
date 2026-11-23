---
name: lateral
description: "Inject random creative perspectives into any question by launching parallel agents, each given a random dictionary word as a lens. Use when a line, angle or diagnosis feels stale or obvious, or when /research or /strategy would benefit from creative reframing. Triggers on 'lateral', 'random angles', 'fresh perspectives', 'creative reframe', 'break it open'."
argument-hint: "[count] [topic or question to explore]"
allowed-tools: Bash(python3 *)
---

# Lateral Thinking via Random Injection

1. **Sample words**: `python3 ~/.claude/skills/lateral/scripts/sample-words.py 10` (default 10; `/lateral 5 <topic>` changes it). Do not re-roll for "better" words; obscure ones force more creative readings. Give obscure words a one-line definition in that agent's prompt.

2. **Launch all agents in one message**, one per word, `model: opus`:

   ```
   You are contributing one perspective to a multi-agent creative synthesis.

   **Topic**: {the user's question or topic}

   **Your assigned random word is: {WORD}**

   Use this word as a creative lens, metaphor, or unexpected connection point to generate a fresh insight about the topic. Interpret the word however produces the most interesting thought: literally, metaphorically, historically, scientifically, etymologically.

   Rules:
   - Give one tight, self-contained insight; the parent is merging ten of these
   - Take a clear position; do not hedge
   - Be original; the value is in unexpected connections
   - Do not explain the exercise or comment on the process
   ```

3. **Synthesise**: the 3 to 5 strongest threads, where two words converged on the same insight, and the consensus or key tension. Chris wants the distilled insight, not ten essays.

Agents use this when a line still feels stale after the spark-table method in `~/vault/agents/references/voice-spark-tables.md`.
