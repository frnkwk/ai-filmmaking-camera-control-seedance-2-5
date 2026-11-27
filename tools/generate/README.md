# tools/generate: one template, any video model

Two scripts, Python standard library only. Run from the repo root. Which models there are and how they differ: [docs/providers.md](../../docs/providers.md).

| Script | What it does | Sends anything? |
|---|---|---|
| `build_request.py` | Reads `templates/<ID>/sent.json` and its prompt, renames the reference tags for the provider, maps the fields, checks the limits, writes `.work/requests/<ID>.<route>.<provider>.<quality>.json`. Exits 1 and writes nothing if a limit is broken. | no |
| `submit.py` | Shows the request and the estimate. With `--yes` it sends it, polls, writes a receipt to `.work/receipts/`, and with `--download` saves the video. `--resume <receipt>` polls again and never resends. | only with `--yes` |

```bash
python3 tools/generate/build_request.py --list
python3 tools/generate/build_request.py CAM06-Orbit --provider magi-2 --url @video1=https://... --url @image1=https://...
python3 tools/generate/submit.py .work/requests/CAM06-Orbit.video.magi-2.draft.json          # look first
WAVESPEED_API_KEY=... python3 tools/generate/submit.py .work/requests/CAM06-Orbit.video.magi-2.draft.json --yes --download
```

## build_request.py options

| Option | Meaning |
|---|---|
| `--provider` | a profile id from `providers/` |
| `--route` | the route in `sent.json` (default `video`; others such as `camera-only-video` or `ink-sketch` where the template has them) |
| `--send` | the send number within the route (default the first) |
| `--quality draft\|final` | the profile's draft or final settings (default `draft`) |
| `--url TAG=URL` | a public URL for a reference, keyed by the tag in the template (`@video1`, `@image1`, ...). Missing ones become placeholders, which `submit.py` refuses. |
| `--prompt-file` | your own prompt. Its `@video1` / `@image1` tags are renamed too. Needed for `h3-max-3d` (2000 characters) and for templates that were never sent; for those the references are taken from the tags in your prompt, and `@video1` is the pill clip. |
| `--duration`, `--ratio`, `--seed` | override the recorded values |
| `--set FIELD=JSON` | any extra field, e.g. `--set target_audio_url='"https://..."'` |

Keys come from the environment variable named in the profile (`FAL_KEY`, `WAVESPEED_API_KEY`, `TEIN_API_KEY`). Never put one in a file in this repo.
