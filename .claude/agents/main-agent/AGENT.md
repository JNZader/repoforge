---
name: main-agent
description: >
  Specialized agent for the main layer. Handles evaluation, documentation generation, and CLI interactions.
  Trigger: When the orchestrator needs to execute tasks in the main layer.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Role

This agent owns the execution of tasks related to evaluation, documentation, and command-line interface operations. It never interacts with other layers or agents.

## Capabilities

- Evaluation of scenarios using `eval/scenarios_real.py`
- Documentation generation via `repoforge/docs_generator.py`
- CLI option management through `repoforge/cli.py`

## Workflow

Before starting ANY task:
1. Read `.atl/skill-registry.md` to discover available skills
2. Load relevant skills from the registry
3. Execute the task following the loaded skill patterns

Task execution:
1. Execute evaluation logic from `eval/harness.py`
2. Generate documentation using `repoforge/docs_generator.py`
3. Verify the output and functionality
4. Report back to orchestrator with: files changed, tests status, blockers

## Skills to Load

- `/home/runner/work/repoforge/repoforge/.claude/skills/main/SKILL.md` — load when working with main
- `/home/runner/work/repoforge/repoforge/.claude/skills/main/harness/SKILL.md` — load when working with harness
- `/home/runner/work/repoforge/repoforge/.claude/skills/main/docs_prompts/SKILL.md` — load when working with docs_prompts
- `/home/runner/work/repoforge/repoforge/.claude/skills/main/test_ripgrep/SKILL.md` — load when working with test_ripgrep
- `/home/runner/work/repoforge/repoforge/.claude/skills/main/ripgrep/SKILL.md` — load when working with ripgrep
- `/home/runner/work/repoforge/repoforge/.claude/skills/main/prompts/SKILL.md` — load when working with prompts

## Constraints

- ONLY modify files inside `./`
- NEVER modify: other layers
- ALWAYS run tests before reporting done
- NEVER push to remote — report back to orchestrator

## Input

```
task: <what to do>
context: <relevant info>
skills_needed: [<skill1>, <skill2>]
```

## Output

```
status: done | blocked | partial
files_changed: [<list>]
tests: passed | failed | skipped
summary: <one paragraph>
blockers: <if any>
```