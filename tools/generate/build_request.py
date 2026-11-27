#!/usr/bin/env python3
"""Build a request for one template send, for any video model with a profile in providers/.

It reads templates/<ID>/sent.json and the prompt that was sent, renames the reference tags to the provider's syntax
(@video1 -> "Video 1" for H3, "@Video1" for MAGI-2, ...), maps the fields, checks the provider's limits, and writes the
request JSON. It never uploads or sends anything: submit.py does that, and only with --yes.

  python3 tools/generate/build_request.py --list
  python3 tools/generate/build_request.py CAM06-Orbit --provider h3-max \
      --url @video1=https://.../CAM06-Orbit.mp4 --url @image1=https://.../me.jpg
  python3 tools/generate/build_request.py CAM06-Orbit --provider h3-max-3d --prompt-file my-intent.txt --url @video1=...

Exit codes: 0 written, 1 a limit is broken or an input is missing (nothing is written).
"""
import argparse, json, os, re, shutil, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROVIDERS = os.path.join(ROOT, "providers")
TAG = re.compile(r"@(video|image|audio)(\d+)\b")


def die(msg):
    print(f"FAIL {msg}", file=sys.stderr)
    sys.exit(1)


def load_profiles():
    out = {}
    for f in sorted(os.listdir(PROVIDERS)):
        if f.endswith(".json"):
            p = json.load(open(os.path.join(PROVIDERS, f), encoding="utf-8"))
            out[p["id"]] = p
    return out


def probe_seconds(path):
    if not os.path.exists(path) or not shutil.which("ffprobe"):
        return None
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                           capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except Exception:
        return None


def synth_send(prompt_file):
    """A template that was never sent: build the reference list from the tags in your own prompt. @video1 is the pill clip."""
    text = open(prompt_file, encoding="utf-8").read()
    tags = sorted({(m.group(1), int(m.group(2))) for m in TAG.finditer(text)}, key=lambda t: (("video", "image", "audio").index(t[0]), t[1]))
    refs = []
    for i, (kind, n) in enumerate(tags, 1):
        pill = kind == "video" and n == 1
        refs.append({"order": i, "kind": kind, "tag_in_prompt": f"@{kind}{n}",
                     "role": "pill clip (the 3D blockout)" if pill else f"your {kind} reference", "file": "pill.mp4" if pill else None})
    return {"n": None, "prompt": {"file": prompt_file}, "references_in_send_order": refs, "parameters": {"sent_as": {}}}


def pick_send(sent, route, n, prompt_file):
    routes = sent.get("routes") or {}
    if route not in routes:
        die(f"route '{route}' not in sent.json; routes: {', '.join(routes) or 'none'}")
    sends = routes[route].get("sends") or []
    if not sends:
        if prompt_file:
            return synth_send(prompt_file)
        die(f"route '{route}' was never sent ({routes[route].get('note') or 'no note'}): write a prompt and pass --prompt-file and --duration")
    if n is None:
        return sends[0]
    for s in sends:
        if s.get("n") == n:
            return s
    die(f"route '{route}' has no send n={n}; sends: {[s.get('n') for s in sends]}")


def retag(prompt, mapping):
    missing = sorted({m.group(0) for m in TAG.finditer(prompt) if m.group(0) not in mapping})
    if missing:
        die(f"the prompt names {', '.join(missing)} but the send has no such reference")

    def sub(m):
        new = mapping[m.group(0)]
        # A tag at the start of a sentence keeps a capital when the provider tag is prose ("the source video").
        start = m.start() == 0 or prompt[max(0, m.start() - 2):m.start()] in (". ", ".\n", "\n\n") or prompt[m.start() - 1] == "\n"
        return new[0].upper() + new[1:] if start and new[:1].islower() else new
    return TAG.sub(sub, prompt)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("template", nargs="?", help="template id, e.g. CAM06-Orbit")
    ap.add_argument("--provider", help="profile id in providers/ (see --list)")
    ap.add_argument("--list", action="store_true", help="list the provider profiles and exit")
    ap.add_argument("--route", default="video", help="route in sent.json (default: video)")
    ap.add_argument("--send", type=int, help="send number n within the route (default: the first)")
    ap.add_argument("--quality", choices=("draft", "final"), default="draft", help="default: draft")
    ap.add_argument("--prompt-file", help="use this prompt instead of the recorded one (its @video1/@image1 tags are renamed too)")
    ap.add_argument("--url", action="append", default=[], metavar="TAG=URL", help="public URL for a reference, e.g. @video1=https://...")
    ap.add_argument("--duration", type=float, help="output seconds (default: the recorded duration)")
    ap.add_argument("--ratio", help="aspect ratio (default: the recorded one)")
    ap.add_argument("--seed", type=int, help="seed, where the provider has one")
    ap.add_argument("--set", action="append", default=[], metavar="FIELD=JSON", help="extra request field, value parsed as JSON when it can be")
    ap.add_argument("--out", help="output file (default: .work/requests/<ID>.<route>.<provider>.<quality>.json)")
    a = ap.parse_args()

    profiles = load_profiles()
    if a.list:
        for p in profiles.values():
            print(f"{p['id']:14} {p['label']}  [{p['status']}]")
        return
    if not a.template or not a.provider:
        ap.error("a template id and --provider are needed (or --list)")
    if a.provider not in profiles:
        die(f"no profile '{a.provider}'; have: {', '.join(profiles)}")
    P = profiles[a.provider]
    L, F = P["limits"], P["fields"]

    tdir = os.path.join(ROOT, "templates", a.template)
    if not os.path.isdir(tdir):
        die(f"no template folder templates/{a.template}")
    sent = json.load(open(os.path.join(tdir, "sent.json"), encoding="utf-8"))
    s = pick_send(sent, a.route, a.send, a.prompt_file)
    sent_as = (s.get("parameters") or {}).get("sent_as") or {}
    errors, warnings = [], []

    # prompt
    pfile = a.prompt_file or os.path.join(tdir, (s.get("prompt") or {}).get("file") or "")
    if not pfile or not os.path.isfile(pfile):
        die(f"no prompt file ({pfile or 'none recorded'}); pass --prompt-file")
    prompt = open(pfile, encoding="utf-8").read().strip()

    # references, renumbered per kind in send order
    refs = sorted(s.get("references_in_send_order") or [], key=lambda r: r.get("order", 0))
    urls = {}
    for u in a.url:
        if "=" not in u:
            die(f"--url needs TAG=URL, got {u}")
        k, v = u.split("=", 1)
        urls["@" + k.lstrip("@").lower()] = v
    mapping, lists, count = {}, {"video": [], "image": [], "audio": []}, {"video": 0, "image": 0, "audio": 0}
    seconds = {"video": [], "audio": []}
    placeholders = []
    for r in refs:
        kind, old = r["kind"], r.get("tag_in_prompt")
        if P["tags"].get(kind) is None or F.get(kind) is None:
            errors.append(f"{a.provider} takes no {kind} reference, and this send has {old} ({r.get('role')})")
            continue
        count[kind] += 1
        if old:
            mapping[old] = P["tags"][kind].format(n=count[kind])
        url = urls.pop(old, None) if old else None
        if not url:
            url = f"<URL for {old}: {r.get('role')}, file {r.get('file')}>"
            placeholders.append(old)
        lists[kind].append(url)
        if kind in seconds:
            d = (r.get("file_info") or {}).get("duration_s")
            if d is None and ("pill clip" in (r.get("role") or "") or r.get("file") == "pill.mp4"):
                d = probe_seconds(os.path.join(tdir, "pill.mp4"))
            if d is None:
                warnings.append(f"length of {old} ({r.get('file')}) unknown: check it is within {L.get(kind + '_each_s')} s")
            else:
                seconds[kind].append(d)
    for k in urls:
        errors.append(f"--url {k} names no reference of this send")
    prompt = retag(prompt, mapping)

    # limits
    if L.get("prompt_chars") and len(prompt) > L["prompt_chars"]:
        errors.append(f"prompt is {len(prompt)} characters, {a.provider} takes {L['prompt_chars']}: write a shorter one and pass --prompt-file")
    for kind, cap in (("video", "videos"), ("image", "images"), ("audio", "audios")):
        n = len(lists[kind])
        if n and L.get(cap) is not None and n > L[cap]:
            errors.append(f"{n} {kind} references, {a.provider} takes {L[cap]}")
        if kind in seconds and seconds[kind]:
            lo, hi = L.get(kind + "_each_s") or (0, 1e9)
            for d in seconds[kind]:
                if not lo <= d <= hi:
                    errors.append(f"a {kind} reference is {d:.2f} s, {a.provider} takes {lo} to {hi} s each")
            tot = sum(seconds[kind])
            if L.get(kind + "_total_s") and tot > L[kind + "_total_s"]:
                longer = [k for k, q in profiles.items() if k != a.provider and (q["limits"].get("video_total_s") or 0) >= tot]
                errors.append(f"{kind} references add up to {tot:.2f} s, {a.provider} takes {L[kind + '_total_s']} s in all"
                              + (f" (split the template into shorter clips, or use {' / '.join(longer) or 'another model'})" if kind == "video" else ""))
            elif L.get(kind + "_total_warn_s") and tot > L[kind + "_total_warn_s"]:
                warnings.append(f"{kind} references add up to {tot:.2f} s, over the {L[kind + '_total_warn_s']} s margin this repo keeps for {a.provider}")
    if L.get("files_total") and sum(len(v) for v in lists.values()) > L["files_total"]:
        errors.append(f"more than {L['files_total']} reference files")

    duration = a.duration if a.duration is not None else sent_as.get("duration")
    if F.get("duration"):
        if duration is None:
            errors.append("no recorded duration; pass --duration")
        else:
            lo, hi = L["duration"]
            if not lo <= duration <= hi:
                errors.append(f"duration {duration} s, {a.provider} makes {lo} to {hi} s")
            if L.get("duration_integer"):
                duration = int(round(duration))
            if seconds["video"] and abs(seconds["video"][0] - duration) > 0.75:
                warnings.append(f"output {duration} s differs from the pill clip ({seconds['video'][0]:.2f} s): the camera timing will not line up")
    ratio = a.ratio or sent_as.get("aspect_ratio") or sent_as.get("ratio")
    if F.get("ratio") and P.get("ratios") and ratio and ratio not in P["ratios"]:
        errors.append(f"ratio {ratio} not offered by {a.provider} ({', '.join(P['ratios'])})")
    if a.seed is not None and not P.get("seed"):
        errors.append(f"{a.provider} has no seed")

    if errors:
        for e in errors:
            print(f"FAIL {e}", file=sys.stderr)
        sys.exit(1)

    # request
    req = {F["prompt"]: prompt}
    for kind in ("video", "image", "audio"):
        if lists[kind]:
            req[F[kind]] = lists[kind][0] if (kind == "video" and F.get("video_single")) else lists[kind]
    if F.get("duration") and duration is not None:
        req[F["duration"]] = duration
    if F.get("ratio") and ratio:
        req[F["ratio"]] = ratio
    if a.seed is not None:
        req[F["seed"]] = a.seed
    req.update(P.get("fixed") or {})
    req.update(P["quality"][a.quality])
    for kv in a.set:
        k, v = kv.split("=", 1)
        try:
            req[k] = json.loads(v)
        except ValueError:
            req[k] = v

    price, est = P.get("price") or {}, None
    secs = duration if F.get("duration") else (seconds["video"][0] if seconds["video"] else None)
    if price.get("usd_per_output_second") and secs:
        est = round(price["usd_per_output_second"] * secs, 2)
    if not P["quality"][a.quality] and a.quality == "draft":
        warnings.append(f"{a.provider} has no cheaper draft: this run is billed as a full-quality run")

    out = {
        "provider": P["id"], "api": P["api"], "endpoint": P["endpoint"], "auth_env": P["auth_env"],
        "template": a.template, "route": a.route, "send": s.get("n"), "quality": a.quality,
        "status": P["status"], "tag_map": mapping,
        "estimate_usd": est, "price_basis": price or P.get("price_note"),
        "placeholders": placeholders, "warnings": warnings, "notes": P.get("notes", []),
        "request": req,
    }
    path = a.out or os.path.join(ROOT, ".work", "requests", f"{a.template}.{a.route}.{P['id']}.{a.quality}.json")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"wrote {os.path.relpath(path)}")
    print(f"  {P['label']}  ->  {P['endpoint']}")
    print(f"  tags: " + ", ".join(f"{k} -> {v}" for k, v in mapping.items()))
    if est is not None:
        print(f"  estimate: about ${est} ({price.get('source')}, checked {price.get('checked')})")
    for w in warnings:
        print(f"  WARN {w}")
    if placeholders:
        print(f"  needs URLs for: {', '.join(placeholders)} (pass --url TAG=URL); submit.py refuses placeholders")


if __name__ == "__main__":
    main()
