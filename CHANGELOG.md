# Changelog

## 0.2.0 (model-agnostic fork)
- `providers/`: one JSON profile per video model: `seedance-2-5` (Tein), `h3-max` and `h3-max-3d` (MiniMax H3 Max on fal), `magi-2` (Sand AI MAGI-2 on WaveSpeed).
- `tools/generate/build_request.py`: renames a template's reference tags for the model, maps the fields, checks the limits, and writes the request; never sends.
- `tools/generate/submit.py`: shows a request and its estimate, and sends it only with `--yes`; polls, keeps a receipt, can resume.
- `docs/providers.md`: what differs between models and how to add one. README, AGENTS.md and llms.txt no longer assume Seedance.
- `tools/check_repo.py`: drops the upstream bans on naming other hosts; the secret checks stay.
- Nothing in the engine, the templates or the recorded results changed. The new providers are untested with these templates.

## 0.1.0
First public version.
- The engine: three.js inside Remotion, the striped stand-ins (the pin, and the single capsule of the first gallery clips), rigs, post chain, checks. The CC0 rig ships in `engine/cinematic/public/kit/`. A clean checkout renders a pill clip.
- 137 templates, each with its three.js code, pill clip, poster, README and `sent.json`; 93 have the prompts that were sent (238 prompt files) and 92 have Seedance results (release downloads).
- 24 environments, the gallery, the method and the why pages, the 137 answered questions.
- The `cinematic-previs` skill (camera and cut rulebook, stills-first QA). The camera-control MCP and skill are a separate project.
Known gaps are in `docs/known-limits.md`.
