# Current method: full Czech catalogue validation

The 19 October revision validates all 21,085 Czech source records with
`off-calculation-3`, separates optional warnings from calculation blockers,
and routes exceptions to source-label review. See
[the review workflow](method/REVIEW-WORKFLOW.md) for exact semantics,
reproduction, image evidence and correction publication. All records remain
unverified. The earlier release instructions below describe the source snapshot
and previous validation pass; the current build processes the full catalogue.

# LIONNE Czech Open Food Facts method

This self-contained archive contains the exact filtering and normalization
method for the Czech OFF review snapshot. No customer, recipe, activity,
independently captured ingredient, database credential or application code is
included. Products remain unverified source records.

## Exact input

- Official repository: https://huggingface.co/datasets/openfoodfacts/product-database
- Revision: `803f01305a4c302b862f78bef880c4101a3f76ea`
- Immutable Parquet URL: https://huggingface.co/datasets/openfoodfacts/product-database/resolve/803f01305a4c302b862f78bef880c4101a3f76ea/food.parquet
- Input SHA-256: `f589c258256ab1e08c584270f4e10cc5dd921a3732c887bbbf7442f6e1b5365a`
- Country filter: `en:czech-republic`
- Rules: `off-cz-preview-2`
- Expected records: 21,085
- Expected records.ndjson SHA-256: `7402877b6edca447c69287cb1a93bcc0c06caffb119d6a7dfb5349e802250827`

## Reproduce the data

Use Python 3.9 or newer. The verified worldwide download is approximately 8 GB.
The method does not call LIONNE services or require an account or secret.

```sh
cd method
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python download.py --revision 803f01305a4c302b862f78bef880c4101a3f76ea --output food.parquet
.venv/bin/python build.py --revision 803f01305a4c302b862f78bef880c4101a3f76ea --parquet food.parquet --output reproduced-cz
```

The manifest records file checksums and the transformation allowlist. Build
timestamps can differ; normalized records must match the checksum above.
The preserved method README explains all checks, conversions and missing-value
semantics. Its historical publication caveat does not override this archive's
MIT licence for the included method files.

## Publication route

This is prepared for the method/alterations option in ODbL section 4.6(b).
It is not an assertion that every use of the resulting data is legally cleared.
Before public use, host this complete archive at a stable public URL and link
it from OFF attribution in the application. Confirm that recipients can obtain
the exact upstream input and any additional contents needed for reconstruction.
This snapshot uses no proprietary additional contents. Retain old method
versions while their corresponding source data remains in use.

A local archive or a private repository does not constitute public availability.
Source changes must produce a new method/release with new checksums. This
release contains no daily-delta processing, correction submission or consumer
API. App access controls do not limit the rights granted under the ODbL.
See NOTICES.md for the separate source and image licences.


## Calculation validation — 18 October 2026

The original 21,085-record review catalogue remains separate. This extension
checks the 9,469 preliminary-pass records against the official full JSON source,
which includes comparison modifiers omitted by the Parquet projection. Only
passing records become eligible for calculations; they remain **unverified**.
No proprietary corrections, customer information or private recipe data enter
this method or the published evidence.

The reproducible inputs are the original Parquet release above, the pinned
worldwide JSONL export in `validation-source.json`, and the 150 preserved,
allowlisted live API responses in `evidence/pilot-20261018/`. The pilot includes
100 preliminary-pass, 25 review and 25 incomplete products, chosen by sorting
SHA-256 of source-qualified IDs within each group. It is not a random estimate
of overall catalogue accuracy. The full cohort uses export evidence, including the newer nutrition schema.
For pilot products the live evidence must also pass, with the same product revision. No live requests are needed to reproduce this run.

From this repository root, after reproducing the original catalogue:

```sh
python3 method/download-jsonl.py   'https://openfoodfacts-ds.s3.eu-west-3.amazonaws.com/openfoodfacts-products.jsonl.gz?versionId=VILumlWXh8J9mlPCmokEeMpO11A6lEpI'   products-20261018.jsonl.gz
python3 method/filter-jsonl.py method/reproduced-cz/records.ndjson   products-20261018.jsonl.gz filtered.ndjson
python3 method/validation-tests.py
python3 method/build-validation.py   --records method/reproduced-cz/records.ndjson   --pilot evidence/pilot-20261018   --bulk filtered.ndjson --bulk-manifest validation-source.json   --output validated-cz --checked-at 2026-10-18T22:00:00Z   --release off-cz-803f01305a4c-7402877b6edc   --method-url https://github.com/Richarrd82/lionne-off-import/tree/REPLACE_WITH_THIS_COMMIT
```

Replace the final placeholder with the immutable commit containing these files.
The manifest pins that method URL; the record content hash and validation ID
are deterministic for these inputs. Reports count source differences including
newly understood qualifiers, not just upstream numeric edits. The conservative
rules withhold any ambiguous basis, prepared/serving-only nutrition, missing
core value, changed nutrition, qualifier, invalid barcode, upstream error or
plausibility failure. They never infer food density, change missing values to
zero, or convert a less-than bound into an exact number. Qualified values retain
their operator, bound and reported units in the evidence.

`_100g` nutrient fields are normalized OFF values, including for explicit
100 ml records; input-unit metadata is checked but is not applied a second
time. A 100g entry with volume-package or beverage hints requires label review.
The only energy conversion is explicit kJ / 4.184. Canonical GTIN aliases with
conflicting eligible nutrition are withheld. Passing the rules is not a
claim of label accuracy or current Czech store availability.

`fetch-pilot.py` is provided for future runs and uses a 4.2-second interval,
respecting the published 15 product requests/minute limit. Large refreshes use
exports; the app does not call OFF once per search. A future run needs its own
pinned inputs, evidence and publication. Old commits remain available for saved
source revisions. The same ODbL/DbCL and image notices above apply to all added
evidence and outputs; MIT applies only to code. Source method publication does
not itself settle the legal status of every combined use or exported recipe.


### Both nutrition schema versions

Rules `off-calculation-2` support legacy `nutriments` and the 3.5+
`nutrition.aggregated_set` representation. The latter gives explicit preparation,
per-100 basis and per-nutrient source, all retained in evidence. Its declared
`value` takes precedence; `value_computed` never fills a missing label value.
Estimated or unrecognized nutrient sources and non-normalized aggregate units
are withheld. Recognized aggregate sources are packaging, manufacturer and
USDA; automatic acceptance does not turn them into human-verified values.
The original legacy live pilot remains published; each full-cohort pilot row
retains the independent live comparison and source hash. The bulk source
preserves fields not returned by the older API representation.

Schema references (OFF-maintained primary documentation):
- https://openfoodfacts.github.io/documentation/docs/Product-Opener/schemas/schemas/product_nutrition_v3.5/
- https://github.com/openfoodfacts/openfoodfacts-server/blob/main/docs/api/ref-api-and-product-schema-change-log.md

