---
name: jx-joyer-image
description: Use when JD colleagues describe any ecommerce image creation or editing need, including product image sets, detail pages, free-form generation, reference edits, batch edits, derivatives, or hit-image replicas through the internal Oxygen models.
---

# JX Joyer Image

Treat the user's natural-language request and supplied images as the interface. Use the bundled Python workflows behind the scenes; the user does not need to understand Skills, CLI commands, JSON, models, or API endpoints.

## Default novice experience

1. Resolve all paths relative to the directory containing this `SKILL.md`.
2. If `.venv/Scripts/python.exe` is missing, tell the user that local dependencies will be prepared, then run `powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1` from the Skill root. This setup must not call a model.
3. Infer the workflow from the request and supplied files. Do not ask novice users to choose a CLI command, workflow name, JSON schema, model, endpoint, or image API.
4. Ask only for information required to produce a useful result and not safely inferable from context, such as the source product image or the intended change.
5. Build the smallest task JSON in the approved output directory. Do not expose the JSON unless the user asks for technical details.
6. Estimate usage before every quota-consuming operation. For task-file workflows, run `estimate`; for a direct single-image derivative, report one image request. Explain the expected text and image request counts in Chinese.
7. Wait for explicit confirmation before adding `--yes` or making any model request.
8. Invoke the CLI through `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1 -- <arguments>`. When a Key is missing, the wrapper provides a masked terminal prompt. Never ask the user to paste a Key into chat.
9. Return generated image paths and a short Chinese summary. Hide implementation details unless requested.

## Automatic routing

- A new image without references: use `workbench` so request counts can be estimated from a task file.
- A request with one or more reference images: use `workbench` for flexible jobs or `edit` for a single explicit edit.
- A six-image ecommerce set, selling-point copy, 1:1 or 3:4 output: use `ecommerce`.
- Product-detail sections, copy, revisions, restoration, or long-image export: use `detail`.
- The same edit across multiple source images: use `batch-edit`.
- Recreating a hit-image layout or template: use `replica`.
- A follow-up change to an existing result: use `derive` or the workflow-specific derivative action.

Read `references/capabilities.md` only when routing is unclear, `references/task-schema.md` when constructing a task file, and `references/commands.md` for exact arguments.

## Fixed service configuration

- Gateway: `http://llm-gw.jd.local/v1`
- Text model: `GPT-5.6-Sol-joybuilder`
- Image model: `GPT-image-2-joybuilder`
- No reference image: `/images/generations`
- One or more reference images: `/images/edits`

Do not let users override these values.

## Safety

- Require JD intranet or VPN access for live calls.
- Read the Oxygen Key only from `JD_LLM_API_KEY` in the current process. The wrapper may set it temporarily from masked input and must clear it afterward.
- Never put a real Key in files, arguments, logs, screenshots, manifests, clipboard instructions, or chat.
- Never create a blank reference image to simulate text-to-image.
- Keep generated artifacts inside the user-approved output directory.
- Do not depend on the Space website, ERP identity, browser storage, `/app/data`, external merchant systems, COS/CDN, or a desktop client.
- Read `references/security.md` before troubleshooting authentication, logging, or file handling.
