# Choosing a video model

The pill method needs one thing from a video model: **it must take a reference video and follow its camera**. Everything else (the engine, the 137 templates, the pill clips, the prompts, the checks in `tools/seedance/`) does not depend on the model. This fork adds a provider layer so the same template can be sent to any model that has a profile in [`providers/`](../providers/).

| Profile | Model and host | Reference video | Output | Draft | Seed | Status |
|---|---|---|---|---|---|---|
| `seedance-2-5` | Seedance 2.5 on Tein | up to 10, 30 s in all (keep under 29 s) | 4 to 30 s | 480p draft, finalize later | no | tested: every result in this repo |
| `h3-max` | MiniMax H3 Max, reference to video, on fal | up to 3, 2 to 15 s each, 15 s in all | 0.92 to 15 s, 480P / 768P / 1080P | a 480P run | yes | untested with pills |
| `h3-max-3d` | MiniMax H3 Max, 3D to video, on fal | exactly 1, up to 15 s and 32 shots | the source clip's length and shape | a 480P run | no | untested with pills |
| `magi-2` | Sand AI MAGI-2, reference to video, on WaveSpeed | up to 5, 2 to 30 s each, 30 s in all | 4 to 30 s, 1080p only | none | yes | untested with pills |

"Untested" means these exact templates have not been run on that model yet. The prompts were written and tuned against Seedance 2.5; expect to adjust them. Run one short draft and check it against the pill clip (`tools/seedance/compare.py`, `qa_cuts.py`, `qa_framing.py`) before sending anything long.

## The flow

```bash
# 1. Build the request. Nothing is uploaded or sent. It renames the tags, maps the fields and checks the limits.
python3 tools/generate/build_request.py CAM06-Orbit --provider h3-max \
  --url @video1=https://.../CAM06-Orbit.mp4 --url @image1=https://.../your-photo.jpg

# 2. Look at it (prints the request and the estimate, sends nothing).
python3 tools/generate/submit.py .work/requests/CAM06-Orbit.video.h3-max.draft.json

# 3. Send it, wait, keep a receipt, download.
FAL_KEY=... python3 tools/generate/submit.py .work/requests/CAM06-Orbit.video.h3-max.draft.json --yes --download
```

The URLs must be public HTTPS addresses of files you uploaded yourself: the fal MCP's `upload_file` or fal's storage for fal, WaveSpeed's `/api/v3/media/uploads` for MAGI-2, Tein's `/v1/uploads` for Seedance. Use the full 1280x534 pill clip from `tools/render-pill.sh`, not the smaller gallery copy. With the fal MCP you can also skip `submit.py`: give the MCP the `request` object from the built file and the endpoint id.

All options: [tools/generate/README.md](../tools/generate/README.md).

## What changes between models

**Reference tags.** The templates name their references `@video1`, `@image1`, `@image2`, `@audio1`. The builder rewrites them per profile and numbers them within each kind in send order:

| In the template | `seedance-2-5` | `h3-max` | `magi-2` | `h3-max-3d` |
|---|---|---|---|---|
| `@video1` | `@video1` | `Video 1` | `@Video1` | `the source video` |
| `@image1` | `@image1` | `Image 1` | `@Image1` | `reference image 1` |
| `@audio1` | `@audio1` | `Audio 1` | `@Audio1` | not accepted |

**Length.** H3 takes 15 s of reference video and makes at most 15 s. 12 templates with a recorded send are longer (16 to 30 s) and are refused for `h3-max`: send them to `magi-2` or `seedance-2-5`, or cut the template in two and send each part. A sweep of the 93 templates with a recorded send: 93 fit `seedance-2-5`, 91 fit `magi-2` (SHOW01's prompt is 87 characters too long, STORY03 uses `adaptive`), and 81 fit `h3-max`. The 44 templates that were never sent (mostly the locked-off camera studies) need your own prompt (`--prompt-file` and `--duration`).

**Drafts.** Only Seedance on Tein has a real draft that can be finalized. On H3 a draft is a 480P run; pass the same `--seed` at `--quality final` for a close (not identical) final. MAGI-2 renders 1080p every time, so a first try costs the full price.

**Prices** (checked 27 Nov 2026, they change): H3 Max on fal about $0.05 per output second; MAGI-2 on WaveSpeed about $0.08 per output second; Seedance on Tein see [costs.md](costs.md). The builder prints an estimate from the profile; check the provider before you rely on it.

## MiniMax H3 Max (fal)

Endpoint `minimax/h3-max/reference-to-video`, key `FAL_KEY`. Fields: `prompt`, `reference_video_urls`, `reference_image_urls`, `reference_audio_urls` (12 files in all), `duration`, `aspect_ratio` (21:9 is offered), `resolution`, `seed`, `prompt_expansion_mode`. The profile turns prompt expansion off so the long template prompt reaches the model as written; set `--set prompt_expansion_mode='"balanced"'` to compare. Other routes on the same model that may be useful: `image_url` / `end_image_url` (first and last frame), `target_audio_url` (a fixed soundtrack for a speaking shot).

## MiniMax H3 Max, 3D to video (fal)

Endpoint `minimax/h3-max/3d-to-video`, key `FAL_KEY`. Made for previs renders: the source video sets the layout, camera, motion and timing, and the optional images set the look. This is the closest match to the pill idea, with two limits. The prompt is a short "scene intent" of at most 2000 characters, so the long template prompts do not fit: write a short one (say what each striped capsule is, that no capsule appears in the result, and what the place is) and pass it with `--prompt-file`. And it takes no audio. Without reference images it makes its own (`max_generated_reference_images`).

## Sand AI MAGI-2 (WaveSpeed)

Endpoint `https://api.wavespeed.ai/api/v3/sand-ai/magi-2/reference-to-video`, key `WAVESPEED_API_KEY`. Fields: `prompt` (15000 characters), `images` (10), `videos` (5, 30 s in all), `audios` (5, 30 s in all), `duration` (whole seconds 4 to 30), `aspect_ratio` (21:9 offered), `generate_audio`, `seed`. Results: `GET /api/v3/predictions/{id}/result`. WaveSpeed's examples name images `@Image1`; video and audio tags are not documented, and `@Video1` / `@Audio1` follow the same pattern. Over-long references are trimmed rather than refused. MAGI-2 is also offered by other hosts with other field names: copy `providers/magi-2.json` and change the endpoint, fields and `api`.

## Adding another model

1. Copy a profile in `providers/` and change `id`, `endpoint`, `auth_env`, `tags`, `fields`, `fixed`, `quality`, `limits`, `ratios`, `price`.
2. If the host's job API is not one of `fal`, `wavespeed`, `tein`, add a small adapter class to `tools/generate/submit.py` (submit, poll).
3. Build one short template (`CAM06-Orbit`, 7 s) and check the draft against the pill clip before anything else.
