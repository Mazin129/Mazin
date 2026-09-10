# Vendored: diagram-design

This directory vendors the **diagram-design** skill by **Cathryn Lavery**, used
under the MIT License (see `LICENSE`).

- Source: https://github.com/cathrynlavery/diagram-design
- Version: 2.6 (SKILL.md metadata)
- Included: `SKILL.md` + `references/` (the skill instructions Vio's LLM follows).
- Omitted to keep Vio lean: `assets/` (example HTML), `scripts/` (the project's own
  tests), and the plugin manifests — none are needed at Vio runtime.

Vio loads these Markdown instructions and asks its local LLM to follow them to produce
a self-contained HTML/SVG diagram (`diagramgen.py`). Quality tracks the model: a small
local model (qwen2.5:3b) will be rough; point `VIO_LLM_MODEL`/`VIO_LLM_URL` at a larger
or hosted model for editorial-quality output.
