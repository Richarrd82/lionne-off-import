"""Download one pinned official S3 export in four resumable byte ranges."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

p = argparse.ArgumentParser()
p.add_argument("url")
p.add_argument("output")
args = p.parse_args()
dest = Path(args.output)
with urllib.request.urlopen(urllib.request.Request(args.url, method="HEAD"), timeout=30) as r:
    size = int(r.headers["Content-Length"])
    headers = {k: v for k, v in r.headers.items() if k.lower() in ("etag", "last-modified", "x-amz-version-id", "content-length")}
if "versionId=" not in args.url:
    raise SystemExit("Pin the official export version before downloading")
prefix = dest.with_suffix(".prefix")
if dest.exists() and not prefix.exists() and dest.stat().st_size < size:
    dest.rename(prefix)
start = prefix.stat().st_size if prefix.exists() else 0
if dest.exists() and dest.stat().st_size == size:
    raise SystemExit("Completed export already exists")
parts = []
for i in range(4):
    a = start + (size - start) * i // 4
    b = start + (size - start) * (i + 1) // 4 - 1
    parts.append((dest.with_suffix(f".part{i}"), a, b))
def download(part):
    path, a, b = part
    have = path.stat().st_size if path.exists() else 0
    if have == b - a + 1:
        return
    req = urllib.request.Request(args.url, headers={"Range": f"bytes={a+have}-{b}", "User-Agent": "LIONNE/0.1 (https://github.com/Richarrd82/lionne-off-import)"})
    with urllib.request.urlopen(req, timeout=90) as r, path.open("ab") as out:
        if r.status != 206 or not r.headers.get("Content-Range", "").startswith(f"bytes {a+have}-{b}/"):
            raise RuntimeError("Unexpected byte range")
        shutil.copyfileobj(r, out, 1024 * 1024)
    if path.stat().st_size != b - a + 1:
        raise RuntimeError("Incomplete range; retry this command")
    print(f"Downloaded range {a}-{b}", flush=True)
with ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(download, parts))
sha = hashlib.sha256()
with dest.open("wb") as out:
    for path in ([prefix] if prefix.exists() else []) + [p[0] for p in parts]:
        with path.open("rb") as source:
            while block := source.read(1024 * 1024):
                sha.update(block)
                out.write(block)
manifest = {"url": args.url, "headers": headers, "size": size, "sha256": sha.hexdigest()}
dest.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest), flush=True)
