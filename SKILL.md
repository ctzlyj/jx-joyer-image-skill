---
name: jx-joyer-image
description: Use when JD colleagues ask Codex to create ecommerce product images, product detail images, free-form generations, reference-image edits, batch edits, derivative edits, or hit-image replicas through the internal Oxygen image models.
---

# JX Joyer Image

Use the bundled Python CLI to turn a user request into the smallest matching JX Joyer workflow.

## Route the request

- Free-form text-to-image: `generate` or `workbench`.
- One or more reference images: `edit`.
- Six-image ecommerce sets: `ecommerce`.
- Product detail sections: `detail`.
- Repeated edits across source images: `batch-edit`.
- Hit-image template recreation: `replica`.
- Follow-up changes to an existing result: `derive`.

Read `references/capabilities.md` to choose a workflow, `references/task-schema.md` to build complex inputs, and `references/commands.md` before invoking the CLI.

## Required execution pattern

1. Inspect user-provided images and requirements.
2. Build the smallest task JSON that satisfies the request.
3. Run `jx-joyer estimate --task-file <file>` without a Key or model call.
4. Tell the user the expected text and image request counts.
5. Obtain explicit confirmation before any quota-consuming call.
6. Set `JD_LLM_API_KEY` only in the process environment and run the selected command with `--yes`.
7. Return output paths and a concise task summary; do not expose credentials or full Data URLs.

## Safety

- Require JD intranet or VPN access.
- Read the Oxygen Key only from `JD_LLM_API_KEY`.
- Never put a real Key in files, arguments, logs, screenshots, manifests, or chat.
- Use `/images/generations` when there is no reference image and `/images/edits` when references exist. Never synthesize a blank reference image.
- Keep generated artifacts inside the user-approved output directory.
- Read `references/security.md` before troubleshooting authentication, logging, or file handling.
