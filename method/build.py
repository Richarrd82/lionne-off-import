#!/usr/bin/env python3
"""Build an OFF-only Czech coverage package from an immutable official snapshot.

No database writes. Remote Parquet reads use HTTP ranges and selected columns.
Use --input for a previously extracted NDJSON file (no network/duckdb needed).
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import shutil
import urllib.request
from datetime import datetime, timezone
from normalize import RULES_VERSION, canonical, digest, project, sample, summarize

FIELDS = ["code", "product_name", "brands", "quantity", "product_quantity_unit", "serving_size", "nutrition_data_per", "nutriments", "images", "countries_tags", "categories_tags", "stores", "ingredients_text", "allergens_tags", "traces_tags", "data_quality_errors_tags", "data_quality_warnings_tags", "no_nutrition_data", "obsolete", "rev", "last_modified_t", "lang"]
REPOSITORY = "https://huggingface.co/datasets/openfoodfacts/product-database"
METHOD_FILES = ["build.py", "download.py", "normalize.py", "requirements.txt", "README.md"]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=pathlib.Path)
    p.add_argument("--input", type=pathlib.Path)
    p.add_argument("--parquet", type=pathlib.Path, help="Verified local Parquet from download.py")
    p.add_argument("--revision", help="Immutable 40-character Hugging Face commit")
    p.add_argument("--country", default="en:czech-republic", choices=["en:czech-republic", "en:slovakia"])
    args = p.parse_args()
    if args.input and args.parquet:
        raise SystemExit("Choose --input or --parquet, not both.")
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "manifest.json").exists():
        raise SystemExit("Completed package already exists. Choose a new output directory; snapshots are immutable.")
    if args.input and not args.revision:
        raise SystemExit("--input requires the upstream --revision recorded when extracting it.")
    revision = args.revision
    if not revision:
        with urllib.request.urlopen("https://huggingface.co/api/datasets/openfoodfacts/product-database", timeout=30) as r:
            revision = json.load(r)["sha"]
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise SystemExit("Expected an immutable upstream commit hash.")
    url = f"{REPOSITORY}/resolve/{revision}/food.parquet"
    raw_path = args.output / "source.ndjson"
    if args.input:
        rows = (json.loads(line) for line in args.input.open() if line.strip())
    else:
        import duckdb
        c = duckdb.connect()
        if args.parquet:
            evidence=json.loads(args.parquet.with_suffix('.source.json').read_text())
            if evidence['revision']!=revision or evidence['url']!=url or args.parquet.stat().st_size!=evidence['size']:
                raise ValueError('Local snapshot evidence does not match the requested release')
            h=hashlib.sha256()
            with args.parquet.open('rb') as f:
                while data:=f.read(8*1024*1024):h.update(data)
            if h.hexdigest()!=evidence['sha256']:raise ValueError('Local snapshot checksum failed')
        else:
            extensions = args.output.parent / "duckdb-extensions"
            extensions.mkdir(exist_ok=True)
            c.execute("SET extension_directory=?", [str(extensions.resolve())])
            c.execute("INSTALL httpfs"); c.execute("LOAD httpfs");c.execute("SET http_timeout=120")
        c.execute("SET threads=4"); c.execute("SET memory_limit='768MB'")
        print(f"Reading official snapshot {revision}; country {args.country}", flush=True)
        query = 'SELECT ' + ','.join('"' + x + '"' for x in FIELDS) + ' FROM read_parquet(?) WHERE list_contains(countries_tags, ?)'
        cursor = c.execute(query, [str(args.parquet) if args.parquet else url, args.country])
        def stream():
            while True:
                batch = cursor.fetchmany(500)
                if not batch:
                    return
                for row in batch:
                    yield dict(zip(FIELDS, row))
        rows = stream()
    records, seen = [], set()
    with raw_path.with_suffix(".partial").open("w") as output:
        for product in rows:
            if args.country not in (product.get("countries_tags") or []):
                continue
            # Explicit allowlist: never export account fields or arbitrary enrichment.
            product = {k: product.get(k) for k in FIELDS}
            code = str(product.get("code") or "")
            if not code or code in seen:
                raise ValueError("Missing or duplicate source code; investigate rather than overwrite.")
            seen.add(code)
            output.write(canonical(product) + "\n")
            records.append(project(product))
    raw_path.with_suffix(".partial").replace(raw_path)
    records.sort(key=lambda x: x["id"])
    normalized = args.output / "records.ndjson"
    with normalized.open("w") as output:
        for row in records:
            output.write(canonical(row) + "\n")
    sha = lambda path: hashlib.file_digest(path.open("rb"), "sha256").hexdigest() if hasattr(hashlib, "file_digest") else hashlib.sha256(path.read_bytes()).hexdigest()
    method = args.output / "method"
    method.mkdir(exist_ok=True)
    for name in METHOD_FILES:
        shutil.copyfile(pathlib.Path(__file__).with_name(name), method / name)
    report = summarize(records)
    (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    manifest = {"format": "lionne.off.source-package.v1", "source": "open_food_facts", "country": args.country,
                "upstreamRevision": revision, "upstreamURL": url, "createdAt": datetime.now(timezone.utc).isoformat(),
                "rulesVersion": RULES_VERSION, "rulesSHA256": sha(pathlib.Path(__file__).with_name("normalize.py")), "projectionFields": FIELDS,
                "license": "ODbL-1.0", "contentsLicense": "DbCL-1.0", "attribution": "Open Food Facts contributors",
                "licenseURL": "https://opendatacommons.org/licenses/odbl/1-0/", "count": len(records),
                "files": {"source.ndjson": sha(raw_path), "records.ndjson": sha(normalized), "report.json": sha(args.output / "report.json"), **{"method/" + name: sha(method / name) for name in METHOD_FILES}}, "previewOnly": True,
                "limitations": ["Country membership is crowdsourced, not proof of current stock.", "Parquet omits some fields, including nutrient comparison modifiers; validate original label/API evidence before activation.", "Unknown units and preparation are not inferred; complete numbers are not verified nutrition.", "Photos are references only; availability and credits must be checked before catalogue activation."]}
    preview = {"format": "lionne.off.preview.v1", "manifest": manifest, "report": report, "products": sample(records)}
    for filename, value in [("report.json", report), ("preview.json", preview), ("manifest.json", manifest)]:
        (args.output / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
