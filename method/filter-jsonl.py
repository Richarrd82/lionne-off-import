"""Stream official JSONL gzip and retain OFF-only evidence for the source import."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
from normalize import canonical
from validate import project_evidence

p = argparse.ArgumentParser()
p.add_argument("records")
p.add_argument("gzip")
p.add_argument("output")
args = p.parse_args()
codes = {json.loads(x)["sourceID"] for x in Path(args.records).read_text().splitlines()}
seen = set()
pattern = re.compile(rb'"code"\s*:\s*"(\d+)"')
output = Path(args.output)
with gzip.open(args.gzip, "rb") as source, output.with_suffix(".partial").open("w") as out:
    for i, line in enumerate(source):
        matches = pattern.findall(line)
        if any(code.decode() in codes for code in matches):
            product = json.loads(line)
            code = str(product.get("code"))
            if code in codes and code not in seen:
                out.write(canonical(project_evidence(product)) + "\n")
                seen.add(code)
        if (i + 1) % 250000 == 0:
            print(f"Read {i + 1:,} source products; matched {len(seen):,}", flush=True)
output.with_suffix(".partial").replace(output)
print(f"Complete: {len(seen)} matching products; {len(codes - seen)} missing", flush=True)
