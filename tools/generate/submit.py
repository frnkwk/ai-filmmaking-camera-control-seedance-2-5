#!/usr/bin/env python3
"""Send a request made by build_request.py, wait for the result, and keep a receipt. Spends money: it needs --yes.

  python3 tools/generate/submit.py .work/requests/CAM06-Orbit.video.h3-max.draft.json            # shows it, sends nothing
  python3 tools/generate/submit.py .work/requests/CAM06-Orbit.video.h3-max.draft.json --yes      # sends it
  python3 tools/generate/submit.py --resume .work/receipts/<file>.json                           # polls a job again, never resends

The key is read from the environment variable named in the request (FAL_KEY, WAVESPEED_API_KEY, TEIN_API_KEY).
It is never printed or written. Receipts go to .work/receipts/ (ignored by git). Python standard library only.
"""
import argparse, json, os, sys, time, urllib.error, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def http(method, url, key_header, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "camera-control-generate/1", **key_header})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(txt)
        except ValueError:
            return e.code, {"error": txt[:2000]}


# Each adapter: auth header, submit -> job dict, poll(job) -> (done, failed, video_url, raw)
class Fal:
    def auth(self, key): return {"Authorization": f"Key {key}"}

    def submit(self, endpoint, body, h):
        code, r = http("POST", f"https://queue.fal.run/{endpoint}", h, body)
        if code >= 300 or "request_id" not in r:
            raise RuntimeError(f"submit refused ({code}): {json.dumps(r)[:1500]}")
        return {"id": r["request_id"], "status_url": r.get("status_url"), "response_url": r.get("response_url")}

    def poll(self, job, h):
        code, r = http("GET", job["status_url"], h)
        st = (r.get("status") or "").upper()
        if st == "COMPLETED":
            code, res = http("GET", job["response_url"], h)
            if code >= 300 or "video" not in res:
                return True, True, None, res
            return True, False, (res.get("video") or {}).get("url"), res
        return False, code >= 400, None, r


class WaveSpeed:
    def auth(self, key): return {"Authorization": f"Bearer {key}"}

    def submit(self, endpoint, body, h):
        code, r = http("POST", endpoint, h, body)
        d = r.get("data") or {}
        if code >= 300 or not d.get("id"):
            raise RuntimeError(f"submit refused ({code}): {json.dumps(r)[:1500]}")
        return {"id": d["id"], "status_url": f"https://api.wavespeed.ai/api/v3/predictions/{d['id']}/result"}

    def poll(self, job, h):
        code, r = http("GET", job["status_url"], h)
        d = r.get("data") or {}
        st = d.get("status")
        if st == "completed":
            outs = d.get("outputs") or []
            return True, not outs, outs[0] if outs else None, r
        if st in ("failed", "cancelled", "timeout", "deleted"):
            return True, True, None, r
        return False, False, None, r


class Tein:
    def auth(self, key): return {"Authorization": f"Bearer {key}"}

    def submit(self, endpoint, body, h):
        code, r = http("POST", endpoint, h, body)
        if code >= 300 or not r.get("id"):
            raise RuntimeError(f"submit refused ({code}): {json.dumps(r)[:1500]}")
        return {"id": r["id"], "status_url": f"https://api.tein.ai/v1/jobs/{r['id']}"}

    def poll(self, job, h):
        code, r = http("GET", job["status_url"], h)
        st = r.get("status")
        if st == "succeeded":
            d = r.get("data") or []
            return True, not d, d[0].get("url") if d else None, r
        if st in ("failed", "canceled", "cancelled", "expired"):
            return True, True, None, r
        return False, False, None, r


ADAPTERS = {"fal": Fal(), "wavespeed": WaveSpeed(), "tein": Tein()}


def wait(ad, job, h, receipt, rpath, every, limit):
    t0 = time.time()
    while True:
        done, failed, url, raw = ad.poll(job, h)
        if done:
            receipt.update({"finished": time.strftime("%Y-%m-%dT%H:%M:%S"), "failed": failed, "video_url": url, "result": raw})
            json.dump(receipt, open(rpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            if failed:
                print(f"FAILED: {json.dumps(raw)[:1500]}")
                sys.exit(1)
            print(f"done: {url}")
            return url
        if time.time() - t0 > limit:
            print(f"still running after {limit} s; resume with: python3 tools/generate/submit.py --resume {os.path.relpath(rpath)}")
            sys.exit(3)
        time.sleep(every)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("request", nargs="?", help="a file written by build_request.py")
    ap.add_argument("--yes", action="store_true", help="really send it (this spends credits)")
    ap.add_argument("--resume", help="a receipt file: poll its job again (never resends)")
    ap.add_argument("--download", action="store_true", help="also save the video next to the receipt")
    ap.add_argument("--every", type=float, default=10, help="seconds between polls (default 10)")
    ap.add_argument("--timeout", type=float, default=1800, help="give up waiting after this many seconds (default 1800)")
    a = ap.parse_args()

    if a.resume:
        rpath = a.resume
        receipt = json.load(open(rpath, encoding="utf-8"))
        spec = receipt["spec"]
    else:
        if not a.request:
            ap.error("a request file, or --resume")
        spec = json.load(open(a.request, encoding="utf-8"))
        receipt, rpath = None, None

    ad = ADAPTERS.get(spec["api"])
    if not ad:
        sys.exit(f"FAIL no adapter for api '{spec['api']}'")
    def auth():
        key = os.environ.get(spec["auth_env"])
        if not key:
            sys.exit(f"FAIL set {spec['auth_env']} in the environment (never in a file in this repo)")
        return ad.auth(key)

    if not a.resume:
        if spec.get("placeholders"):
            sys.exit(f"FAIL these references still have no URL: {', '.join(spec['placeholders'])} (rebuild with --url)")
        body = spec["request"]
        show = {k: (v[:160] + f"... ({len(v)} chars)" if isinstance(v, str) and len(v) > 200 else v) for k, v in body.items()}
        print(f"{spec['provider']} -> {spec['endpoint']}  [{spec['status']}]")
        print(json.dumps(show, ensure_ascii=False, indent=1))
        est = spec.get("estimate_usd")
        print(f"estimate: {'about $' + str(est) if est is not None else 'unknown, see ' + json.dumps(spec.get('price_basis'))}")
        for w in spec.get("warnings", []):
            print(f"WARN {w}")
        if not a.yes:
            print("nothing sent. Add --yes to send this exact request.")
            sys.exit(2)
        h = auth()
        job = ad.submit(spec["endpoint"], body, h)
        os.makedirs(os.path.join(ROOT, ".work", "receipts"), exist_ok=True)
        rpath = os.path.join(ROOT, ".work", "receipts",
                             f"{spec['template']}.{spec['route']}.{spec['provider']}.{time.strftime('%Y%m%d-%H%M%S')}.json")
        receipt = {"spec": spec, "job": job, "queued": time.strftime("%Y-%m-%dT%H:%M:%S")}
        json.dump(receipt, open(rpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"queued {job['id']}; receipt {os.path.relpath(rpath)}")

    if a.resume:
        h = auth()
    url = wait(ad, receipt["job"], h, receipt, rpath, a.every, a.timeout)
    if a.download and url:
        dst = os.path.splitext(rpath)[0] + ".mp4"
        urllib.request.urlretrieve(url, dst)
        print(f"saved {os.path.relpath(dst)}")


if __name__ == "__main__":
    main()
