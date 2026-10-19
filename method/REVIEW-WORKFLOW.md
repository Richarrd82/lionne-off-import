# Full-catalogue validation and label review — 19 October 2026

`off-calculation-4` validates every Czech record against the pinned full JSONL
source. The old Parquet quality status is not a permanent eligibility gate.
Products still require a current name, valid matching GTIN, a source revision,
explicit as-sold 100 g/100 ml basis, exact declared core nutrients and plausible
values. Material core/basis conflicts remain held. Missing old values can be filled
from explicit current source values. Unknown optional nutrients stay null;
qualifiers and optional provenance problems become warnings, not food-wide
blocks. Contradictory nutrition remains a blocker. Eligibility is not human
verification. No per-serving or density assumptions are introduced.

Reproduce using the original source manifest and validation-source.json in the
public method repository. `filter-jsonl.py` now preserves image metadata as well
as modern/legacy nutrition. Build all 21,085 rows with `build-validation.py`.
The existing 150-product live pilot is retained and must agree; its observation
timestamps are not changed to suggest a new live fetch.

Nutrition photos are resolved from OFF's versioned selected nutrition crops,
Czech then English then other languages, at most two per product. Image uploader,
revision and CC BY-SA 3.0 attribution are retained. No images are redistributed
by this method archive. The AI reader stores the fetched bytes' SHA-256, photo
reference, literal label quotes, model, response ID, usage and candidate values.
Images are untrusted data. No estimate or AI confidence score substitutes for
visible evidence. Qualified core values remain unusable for exact calculations.

Queue groups: available, label_needed, conflicts, needs_photo, identity. The
private app's aggregate product demand can influence queue priority but does
not enter the source dataset or public method. It stores no search text or
user identity. No-evidence products can be parked until someone needs them.

AI proposals never become automatically eligible. Ten individual accepted
proposals are required before accepting a batch of similar missing/basis
proposals; conflicts always require individual review. This is a workflow
sampling gate, not a measured accuracy guarantee. Each acceptance records the
exact proposal and reviewer privately. Rejected/unclear results remain held.

Accepted review exports contain OFF-only evidence and corrections, no account
IDs, recipe contents, or reviewer events. To apply them use `--reviews FILE`
when building a NEW immutable validation package. Source SHA-256 must match;
old core values, issues, label quotes/photos and the correction digest remain in
the evidence. Optional nutrients are cleared when core/basis changes. Source
identity, calculation bounds, qualifiers, energy and GTIN conflicts are checked
again. Existing recipes continue resolving their original validation ID.

Publish the exact accepted-reviews.json additional contents and updated method
before activating a corrected release, so the derivative can be reconstructed.
The preparation/loading adapter is private application code, not needed for
reconstruction. It never merges OFF data into independently captured foods.
Data remains ODbL 1.0 / DbCL 1.0; photos retain their separate CC BY-SA licence.
The method/alterations publication route does not replace legal review.

## Avoiding unnecessary paid readings

Modern `nutrition.aggregated_set.per` explicitly distinguishes 100g and 100ml;
pack volume must not erase that declared basis. Legacy `nutrition_data_per=100g`
with volume hints remains ambiguous. We do not infer food density or ml from
product names. Floating-point noise and decimal punctuation are not changes.

Small changes between two positive declared numbers (at most 1 kcal / 0.1 g
AND 2% of the smaller value) do not trigger a paid source-conflict check. Exact
current values, prior values, warnings and provenance are retained. This is an
application triage policy, not a legal tolerance or human verification. Zero
crossings, missing values, units, qualifiers and larger changes remain distinct.

The default paid batch excludes complete records needing only basis/preparation
confirmation. Those remain held and have an explicit optional reading scope.
The app shows why a record needs checking and why bulk acceptance is locked,
with a guided individual-review route. The ten-sample gate remains enforced
server-side. Identical image bytes are submitted to AI once; both source image
references and credits remain in the evidence. Existing jobs can carry forward
across rules-only releases only for unchanged source hashes. No accepted
corrections are included in this release.
