"""Build auditable OFF validation and calculation snapshots, no database writes."""
import argparse
from collections import defaultdict
import datetime
import json
from pathlib import Path
from normalize import canonical, digest
from validate import validate, report, RULES, CORE, pilot
from review import label_photos, review_group, apply_accepted_review

p = argparse.ArgumentParser()
p.add_argument("--records", required=True)
p.add_argument("--pilot", required=True)
p.add_argument("--bulk")
p.add_argument("--reviews", help="Accepted OFF-only review export; publish these additional contents with the method")
p.add_argument("--bulk-manifest")
p.add_argument("--output", required=True)
p.add_argument("--method-url", required=True)
p.add_argument("--checked-at", required=True)
p.add_argument("--release", required=True)
args = p.parse_args()
records = [json.loads(x) for x in Path(args.records).read_text().splitlines()]
api = {f.stem: json.loads(f.read_text()) for f in Path(args.pilot).glob("*.json") if f.name != "selection.json"}
bulk = {str(r["code"]): r for r in map(json.loads, Path(args.bulk).read_text().splitlines())} if args.bulk else {}
source_manifest = json.loads(Path(args.bulk_manifest).read_text()) if args.bulk_manifest else None
out = Path(args.output)
out.mkdir(parents=True, exist_ok=True)
if (out / "manifest.json").exists():
    raise SystemExit("Immutable validation package exists; choose a new output")
pilot_rows = [validate(r, api.get(r["sourceID"], {}), api.get(r["sourceID"], {}).get("checkedAt", args.checked_at), "live_api") for r in pilot(records)]
(out / "pilot-report.json").write_text(canonical(report(pilot_rows)) + "\n")
(out / "pilot-results.ndjson").write_text("".join(canonical(r) + "\n" for r in pilot_rows))
(out / "pilot-evidence.ndjson").write_text("".join(canonical({"sourceID": k, **v}) + "\n" for k, v in sorted(api.items())))
selection = records if args.bulk else pilot(records)
validations, sources = [], {}
for r in selection:
    code = r["sourceID"]
    e = api.get(code, {})
    if args.bulk or e.get("status") not in ("found", "not_found"):
        e = {"product": bulk.get(code), "status": "found" if code in bulk else "not_found" if args.bulk else "unavailable"}
        method, checked = "official_jsonl", args.checked_at
    else:
        method, checked = "live_api", e["checkedAt"]
    v = validate(r, e, checked, method)
    live = api.get(code, {})
    if args.bulk and live.get("status") in ("found", "not_found"):
        lv = validate(r, live, live["checkedAt"], "live_api")
        v["liveComparison"] = {"checkedAt": lv["checkedAt"], "sourceRevision": lv["sourceRevision"], "sourceSHA256": lv["sourceSHA256"], "issues": lv["issues"]}
        # The bulk snapshot preserves the newer schema and nutrient provenance;
        # the independent live pilot must also agree before enabling a product.
        v["issues"] = sorted(set(v["issues"] + lv["issues"]))
        if v["sourceRevision"] != lv["sourceRevision"]:
            v["issues"].append("live_pilot_revision_changed")
        v["eligible"] = not v["issues"]
    v["labelPhotos"] = label_photos(e.get("product") or {})
    validations.append(v)
    sources[code] = e.get("product") or {}
groups = defaultdict(list)
for v in validations:
    if v["eligible"]:
        groups[v["gtin14"]].append(v)
for group in groups.values():
    if len({canonical(v["nutrition"]) for v in group}) > 1:
        for v in group:
            v["eligible"] = False
            v["issues"].append("conflicting_gtin_aliases")
for v in validations:
    v["reviewGroup"] = review_group(v)
accepted = json.loads(Path(args.reviews).read_text()) if args.reviews else None
if accepted:
    if accepted.get("format") != "lionne.off.review.v1" or accepted.get("license") != "ODbL-1.0":
        raise ValueError("Invalid OFF correction export")
    by_id = {v["sourceID"]: v for v in validations}
    seen = set()
    for item in accepted["items"]:
        if item["sourceID"] in seen or item["sourceID"] not in by_id:
            raise ValueError("Duplicate or unknown correction")
        seen.add(item["sourceID"])
        apply_accepted_review(by_id[item["sourceID"]], item)
    (out / "accepted-reviews.json").write_text(canonical(accepted) + "\n")
# Recheck alias collisions after corrections as well as after source validation.
groups = defaultdict(list)
for v in validations:
    if v["eligible"]:
        groups[v["gtin14"]].append(v)
for group in groups.values():
    if len({canonical({"basis": v["nutrition"]["basis"], "values": v["nutrition"]["values"]}) for v in group}) > 1:
        for v in group:
            v["eligible"] = False
            v["issues"].append("conflicting_gtin_aliases")
            v["reviewGroup"] = review_group(v)
run = "off-check-" + digest(validations)[:20]
by_code = {r["sourceID"]: r for r in selection}
rows = []
for v in validations:
    food = None
    if v["eligible"]:
        r = by_code[v["sourceID"]]
        source = sources[v["sourceID"]]
        source_ref = {"kind": "open_food_facts", "validationID": run, "releaseID": args.release, "sourceID": v["sourceID"], "sourceRevision": v["sourceRevision"], "rawSHA256": v["sourceSHA256"], "methodURL": args.method_url}
        nutrition = {"id": f"off:{v['sourceID']}:{v['sourceRevision']}:{run}", "ingredientID": v["id"], "revision": v["sourceRevision"],
                     "basis": v["nutrition"]["basis"], "preparation": "as_sold", "verification": "unverified", "verifiedBy": None, "verifiedAt": None,
                     "nutrients": {k: v["nutrition"]["values"][k] for k in CORE},
                     "source": {"kind": "licensed_database", "provider": "open_food_facts", "reference": r["provenance"]["sourceURL"], "observedAt": v["checkedAt"],
                                "license": "ODbL-1.0", "contentsLicense": "DbCL-1.0", "attribution": "Open Food Facts contributors", "revision": v["sourceRevision"], "rawSHA256": v["sourceSHA256"], "validationID": run, "methodURL": args.method_url, "nutrientSources": v["nutrition"]["nutrientSources"]}}
        food = {"id": v["id"], "revision": v["sourceRevision"], "sourceRef": source_ref, "eligible": True, "sourceLabel": "Open Food Facts · automatically checked",
                "document": {"name": v.get("acceptedReview", {}).get("result", {}).get("candidate", {}).get("name") or source.get("product_name_cs") or source.get("product_name_en") or source.get("product_name") or r["name"], "brand": source.get("brands") or r["brand"],
                             "pack": source.get("quantity") or r["pack"], "aliases": [], "category": "Open Food Facts", "portions": [], "barcodes": [v["sourceID"]], "photo": None,
                             "sourcePhoto": r["photo"], "nutrition": nutrition}}
    rows.append({"evidence": v, "food": food})
payload = "".join(canonical(r) + "\n" for r in rows)
(out / "records.ndjson").write_text(payload)
summary = report(validations)
summary["reviewGroups"] = dict(__import__("collections").Counter(v["reviewGroup"] for v in validations))
(out / "report.json").write_text(canonical(summary) + "\n")
manifest = {"format": "lionne.off.validation.v1", "id": run, "source": "open_food_facts", "license": "ODbL-1.0", "contentsLicense": "DbCL-1.0", "rulesVersion": RULES,
            "releaseID": args.release, "checkedAt": args.checked_at, "methodURL": args.method_url, "count": len(rows), "bulk": source_manifest,
            "files": {name: __import__('hashlib').sha256((out / name).read_bytes()).hexdigest() for name in ("records.ndjson", "report.json", "pilot-evidence.ndjson", "pilot-results.ndjson", "pilot-report.json")}}
if accepted:
    manifest["files"]["accepted-reviews.json"] = __import__("hashlib").sha256((out / "accepted-reviews.json").read_bytes()).hexdigest()
(out / "manifest.json").write_text(canonical(manifest) + "\n")
print(json.dumps({"id": run, "report": summary, "pilot": report(pilot_rows)}, indent=2))
