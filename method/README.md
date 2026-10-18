# Open Food Facts Czech coverage importer

Self-contained method for filtering and projecting an immutable official Open
Food Facts snapshot. It reads only OFF data and writes local files. There are no
application database connections, account identifiers, credentials or private
enrichment inputs. The initial output is a coverage preview, not verified food
data suitable for automatic publication.

## Reproduce

Python 3.9+ is required. Create a virtual environment, then install
`requirements.txt`. `download.py` uses the standard library; `build.py` uses
DuckDB only when reading Parquet.

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
python download.py --revision <40-character-commit> --output food.parquet
.venv/bin/python build.py --revision <same-commit> --parquet food.parquet --output release-cz
```

Find a release commit in the official
[product-database repository](https://huggingface.co/datasets/openfoodfacts/product-database).
Download uses eight concurrent bounded range reads, verifies Content-Range and
the complete upstream LFS SHA-256, and saves `.source.json` evidence alongside
the Parquet file. Downloads use `LIONNE-OFF-Preview/1.0` as their User-Agent.
Configure an operator contact in that header before scheduling a public service.
This is one export download, not a website crawl or a product API loop.

Alternatively `build.py --revision <commit> --output release-cz` reads selected
columns directly from remote Parquet. Its many small range requests can be much
slower. `--input release-cz/source.ndjson` replays the selected source records
offline without DuckDB; keep the original `--revision`. Use a new output
directory: completed releases cannot be overwritten.

## Selection and meaning

- Default country filter: exact membership of `en:czech-republic` in
  `countries_tags`. `--country en:slovakia` builds a separate Slovak package.
  Country tags are contributed observations, not proof of current availability,
  country of manufacture or completeness of the country's market.
- Names prefer Czech, English, the primary name, then another available name.
  No translation or nutrient estimation is performed.
- Source IDs are strings. Valid GTIN-8/12/13/14 checksums get a zero-padded
  GTIN-14 match key. Invalid and internal codes remain identifiable and flagged.
  Leading zeros are never removed. Duplicate source IDs abort the build.
- Missing/invalid numbers remain null; zero remains zero. Only the exported
  `100g` column is read, never the prepared or serving column. A missing kcal
  number may be converted from kJ / 4.184; the conversion is recorded.
- `100ml` is a volume basis. `100g` on a volume-labelled pack is flagged because
  the export alone cannot settle the basis. Missing basis and preparation are
  not guessed. Serving and package amounts remain source text.
- Missing or numeric-only name, or any missing core nutrient (kcal, protein,
  carbs, fat), is `incomplete`.
  Other flags cause `needs_review`; remaining rows are
  `passes_preliminary_checks`. Every row remains **unverified** and preview-only.
- Sugars above carbohydrates or saturated fat above fat allow 0.5 g rounding.
  Core macros + fibre + salt above 105 g flag mass-basis records; subnutrients
  are not counted twice. Energy mismatch above max(20 kcal, 15% of declared
  kcal) is a review flag, using 4P + 4C + 9F + 2fibre. Alcohol, polyols and
  rounding can explain differences. These are checks, not correction rules.
- Source quality errors, obsolete rows and invalid GTINs are flagged. Upstream
  warnings remain in the raw projection. No number is repaired to pass a check.
- Selected front photos retain source URL, image revision, original uploader
  credit where available, and CC BY-SA 3.0. Images are referenced, not downloaded
  or edited. Short barcode image paths require later API resolution.

The Parquet export omits some source details, including nutrient comparison
modifiers such as `<`. Resolve original API/label evidence before activating a
record. The release does not implement ongoing synchronization or removals.

## Output and share-alike preparation

`source.ndjson` retains the explicit allowlist of selected source fields.
`records.ndjson` contains the full country projection; `report.json` contains
counts, issues and top 20 brands/categories. `preview.json` contains 100
deterministically selected rows spread across all three quality states; this is
not a representative or popularity-weighted sample.

`manifest.json` records the immutable upstream URL/commit, UTC build time, rules
version, field list and SHA-256 checksums. `method/` preserves the exact scripts,
dependency pin and this README. Replaying the same source with these rules must
produce the same normalized-record checksum; build timestamps can differ.

This folder is prepared as the **method of making the Derivative Database** for
review under [ODbL §4.6](https://opendatacommons.org/licenses/odbl/1-0/). Merely
having this folder locally does not fulfill an offer to public recipients. Before
public use, make the chosen compliant method/alteration package or full
derivative available, with licence notices and any additional contents required
to reconstruct it. Confirm access to the exact input release and the applicable
terms for publishing the method. Do not claim that attribution alone, a separate
SQL table, or publishing incomplete code guarantees compliance.

Data attribution: **Open Food Facts contributors — ODbL 1.0**. Individual
contents: DbCL 1.0. Photos: CC BY-SA 3.0; retain their separate credits and source
links. See the [official licensing guide](https://openfoodfacts.github.io/documentation/docs/Product-Opener/api/tutorials/license-be-on-the-legal-side/).

No public hosting or open-source licence for application code is established by
this preview. Review the final publication arrangement before launch.
