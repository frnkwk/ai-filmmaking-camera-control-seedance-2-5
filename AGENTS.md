# AGENTS.md: AI filmmaking camera control with three.js, for any reference-video model

For AI agents (Claude, Codex, Cursor, others). Read this first.

## What this repo is
A way to control the camera of an AI video. You write the camera move in three.js, render a grey "pill clip" (people are striped pills), and send that clip to a video model (Seedance 2.5, MiniMax H3 Max, Sand AI MAGI-2, ...) as the reference video with a face photo and a prompt. The model copies the camera and invents the people and the place. 137 ready templates, each with code, clip, prompts and results.

## Generate with any model
Each model has a profile in `providers/` (`h3-max`, `h3-max-3d`, `magi-2`, `seedance-2-5`). Build a request with `python3 tools/generate/build_request.py <ID> --provider <profile> --url @video1=... --url @image1=...`: it renames the prompt's reference tags for the model, maps the fields and refuses a request that breaks the model's limits. `tools/generate/submit.py <file>` shows the request and the estimate; only `--yes` sends it. Keys come from the environment (`FAL_KEY`, `WAVESPEED_API_KEY`, `TEIN_API_KEY`), from the person's own account. Never ask for a key in chat, never write it to a file, never commit it. Model differences: `docs/providers.md`. Seedance on Tein: `docs/tein-endpoint.md` and `docs/tein/`. Only Seedance 2.5 has been tested with these templates.

## Rules for agents
1. Never send a request to a video service, and never spend credits, without the person's explicit yes for that exact request. Show the request and the price first.
2. Start with a draft (`--quality draft`: a Tein draft, or a 480P run on H3; MAGI-2 has no draft, so start with a short template), check it against the pill clip, and make a final only when it is right.
3. Move the camera in every clip you send. Hold every shot 2 seconds or more.
4. The stand-in is a striped pill with no limbs. Name every stand-in in the prompt and say no pill appears in the result. Rebuild the set in words.
5. Prompts under `templates/<ID>/prompts/` are examples, and `sent.json` says whether each was the text sent, a recovered copy or a rebuilt one. Rebuild before reuse.

## Where things are
| Need | Open |
|---|---|
| The idea in one page | `docs/idea.md` |
| All the rules, with why | `docs/rules.md` |
| Pick a template | `templates/INDEX.md` (137, with previews), then `templates/<ID>/README.md` |
| Render a pill clip | `cd engine/cinematic && npm install && tools/render-pill.sh <ID>` (Node 22.12+, ffmpeg) |
| Write a prompt | `docs/prompt-anatomy.md` |
| Build your own template | `docs/build-your-own-template.md` |
| Send to a model | `docs/providers.md`, `tools/generate/README.md` (Tein: `docs/tein-endpoint.md`) |
| Costs and limits | `docs/costs.md`, `docs/known-limits.md` |
| Why it works this way | `docs/why/`, `answers/` |
| Check the repo | `python3 tools/check_repo.py .` |

Result videos are release downloads (`release-media/`), not files in git.
