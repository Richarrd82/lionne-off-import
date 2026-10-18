"""150 reproducibly selected current OFF API reads; <= 15/minute, resumable."""
import argparse
import datetime
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
from normalize import canonical
from validate import pilot, project_evidence, SOURCE_FIELDS

p = argparse.ArgumentParser()
p.add_argument("records")
p.add_argument("output")
args = p.parse_args()
records = [json.loads(x) for x in Path(args.records).read_text().splitlines()]
out = Path(args.output)
out.mkdir(parents=True, exist_ok=True)
selection = pilot(records)
(out / "selection.json").write_text(canonical([r["sourceID"] for r in selection]) + "\n")
for i, record in enumerate(selection):
    path = out / (record["sourceID"] + ".json")
    if path.exists() and json.loads(path.read_text()).get("status") != "unavailable":
        continue
    url = "https://world.openfoodfacts.org/api/v3/product/" + record["sourceID"] + ".json?fields=" + ",".join(SOURCE_FIELDS)
    start = time.monotonic()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "LIONNE/0.1 (https://github.com/Richarrd82/lionne-off-import)"})
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.load(response)
        product = body.get("product")
        evidence = {"status": "found" if product else "not_found", "product": project_evidence(product) if product else None}
    except urllib.error.HTTPError as e:
        evidence = {"status": "not_found" if e.code == 404 else "unavailable", "httpStatus": e.code, "product": None}
        if e.code == 429:
            time.sleep(60)
    except Exception as e:
        evidence = {"status": "unavailable", "error": type(e).__name__, "product": None}
    evidence.update({"url": url, "checkedAt": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")})
    path.write_text(canonical(evidence) + "\n")
    if (i + 1) % 10 == 0:
        print(f"Pilot evidence {i + 1}/{len(selection)}", flush=True)
    time.sleep(max(0, 4.2 - (time.monotonic() - start)))
print("Pilot source acquisition complete", flush=True)
