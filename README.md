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
