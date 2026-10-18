"""OFF-only projection rules. No application database, credentials or private data.

Parquet omits some source fields (notably nutrient comparison modifiers). This
projection is a coverage preview, never an approved/verified food import.
"""
import hashlib
import json
import math
import re
from collections import Counter

RULES_VERSION = "off-cz-preview-2"
DATABASE_LICENSE = "https://opendatacommons.org/licenses/odbl/1-0/"
IMAGE_LICENSE = "https://creativecommons.org/licenses/by-sa/3.0/"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def gtin(code):
    if not isinstance(code, str) or not re.fullmatch(r"(?:\d{8}|\d{12,14})", code):
        return None
    check = (10 - sum(int(x) * (3 if i % 2 == 0 else 1) for i, x in enumerate(reversed(code[:-1]))) % 10) % 10
    return code.zfill(14) if check == int(code[-1]) else None


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None


def localized(value):
    if isinstance(value, str):
        return {"text": value.strip(), "language": "unspecified"}
    entries = {x.get("lang"): x.get("text", "").strip() for x in value or [] if isinstance(x.get("text"), str)}
    for lang in ["cs", "en", "main", *sorted(k for k in entries if isinstance(k, str))]:
        if entries.get(lang):
            return {"text": entries[lang], "language": lang}
    return {"text": "", "language": None}


def front_photo(product):
    code = str(product.get("code") or "")
    if not re.fullmatch(r"\d{8,14}", code):
        return None
    images = product.get("images") or []
    selected = [x for x in images if re.fullmatch(r"front_[a-z]{2}", str(x.get("key", ""))) and number(x.get("rev")) is not None]
    selected.sort(key=lambda x: (["front_cs", "front_en", "front_" + str(product.get("lang"))].index(x["key"]) if x["key"] in ["front_cs", "front_en", "front_" + str(product.get("lang"))] else 9, x["key"]))
    if not selected:
        return None
    image = selected[0]
    original = next((x for x in images if str(x.get("key")) == str(image.get("imgid"))), {})
    # OFF's long-code directory layout; short-code paths require API resolution.
    url = None
    if len(code) >= 13:
        path = "/".join([code[:3], code[3:6], code[6:9], code[9:]])
        url = f"https://images.openfoodfacts.org/images/products/{path}/{image['key']}.{image['rev']}.400.jpg"
    return {"url": url, "imageKey": image["key"], "revision": image["rev"], "originalImageID": image.get("imgid"),
            "credit": original.get("uploader") or "Open Food Facts contributors", "license": "CC-BY-SA-3.0", "licenseURL": IMAGE_LICENSE,
            "sourceURL": f"https://world.openfoodfacts.org/product/{code}", "modifiedByLionne": False}


def project(product):
    code = str(product.get("code") or "")
    name = localized(product.get("product_name"))
    nutrients = {x.get("name"): x for x in product.get("nutriments") or []}
    fields = {"kcal": "energy-kcal", "proteinG": "proteins", "carbsG": "carbohydrates", "fatG": "fat", "sugarsG": "sugars", "saturatedFatG": "saturated-fat", "fiberG": "fiber", "saltG": "salt"}
    values = {k: number(nutrients.get(v, {}).get("100g")) for k, v in fields.items()}
    issues = []
    for k, v in fields.items():
        raw = nutrients.get(v, {}).get("100g")
        if raw is not None and number(raw) is None:
            issues.append("invalid_" + k)
    energy_method = "reported_kcal" if values["kcal"] is not None else None
    if values["kcal"] is None and number(nutrients.get("energy-kj", {}).get("100g")) is not None:
        values["kcal"] = nutrients["energy-kj"]["100g"] / 4.184
        energy_method = "converted_from_kj"
    declared = product.get("nutrition_data_per")
    unit = "ml" if declared == "100ml" else "g" if declared == "100g" else None
    # Pack volume is not evidence of the nutrition table's basis or a density.
    if unit == "g" and product.get("product_quantity_unit") in ["ml", "cl", "dl", "l"]:
        unit = None
        issues.append("volume_pack_basis_needs_label")
    if unit is None:
        issues.append("nutrition_basis_needs_label")
    if product.get("no_nutrition_data"):
        issues.append("source_says_no_nutrition")
    if product.get("obsolete"):
        issues.append("obsolete")
    if not gtin(code):
        issues.append("invalid_or_non_gtin_code")
    if not name["text"]:
        issues.append("missing_name")
    if name["text"].isdecimal():
        issues.append("numeric_placeholder_name")
    for child, parent in [("sugarsG", "carbsG"), ("saturatedFatG", "fatG")]:
        if values[child] is not None and values[parent] is not None and values[child] > values[parent] + .5:
            issues.append(child + "_exceeds_" + parent)
    core = [values[k] for k in ["kcal", "proteinG", "carbsG", "fatG"]]
    complete = all(v is not None for v in core)
    if unit == "g" and all(v is not None for v in core[1:]) and sum(core[1:]) + (values["fiberG"] or 0) + (values["saltG"] or 0) > 105:
        issues.append("mass_sum_exceeds_100g_tolerance")
    if complete:
        energy = 4 * values["proteinG"] + 4 * values["carbsG"] + 9 * values["fatG"] + 2 * (values["fiberG"] or 0)
        # A review hint only: alcohol/polyols and rounding can explain differences.
        if abs(values["kcal"] - energy) > max(20, .15 * values["kcal"]):
            issues.append("energy_needs_review")
    upstream = product.get("data_quality_errors_tags") or []
    if upstream:
        issues.append("upstream_quality_error")
    status = "incomplete" if not complete or not name["text"] or name["text"].isdecimal() else "needs_review" if issues else "passes_preliminary_checks"
    return {"id": "off:" + code, "source": "open_food_facts", "sourceID": code, "gtin14": gtin(code),
            "name": name["text"] or "Unnamed product", "nameLanguage": name["language"], "brand": product.get("brands") or "",
            "pack": product.get("quantity"), "servingText": product.get("serving_size"), "stores": product.get("stores"),
            "countries": product.get("countries_tags") or [], "categories": product.get("categories_tags") or [],
            "ingredients": localized(product.get("ingredients_text")), "allergens": product.get("allergens_tags") or [],
            "traces": product.get("traces_tags") or [], "photo": front_photo(product),
            "nutrition": {"basis": {"amount": 100, "unit": unit}, "declaredBasis": declared,
                          "preparation": "as_sold_export_column_unconfirmed", "values": values, "energyMethod": energy_method},
            "quality": {"status": status, "coreComplete": complete, "verification": "unverified", "issues": issues, "upstreamErrors": upstream},
            "provenance": {"sourceURL": f"https://world.openfoodfacts.org/product/{code}", "revision": product.get("rev"),
                           "lastModifiedUnix": product.get("last_modified_t"), "license": "ODbL-1.0", "licenseURL": DATABASE_LICENSE,
                           "contentsLicense": "DbCL-1.0", "attribution": "Open Food Facts contributors", "rawSHA256": digest(product)},
            "previewOnly": True}


def summarize(records):
    statuses = Counter(x["quality"]["status"] for x in records)
    return {"total": len(records), "coreComplete": sum(x["quality"]["coreComplete"] for x in records),
            "withFrontPhoto": sum(x["photo"] is not None for x in records), "withCzechName": sum(x["nameLanguage"] == "cs" for x in records),
            "validGTIN": sum(x["gtin14"] is not None for x in records), "statuses": dict(statuses),
            "issues": dict(Counter(i for x in records for i in x["quality"]["issues"]).most_common()),
            "topBrands": dict(Counter(b.strip() for x in records for b in x["brand"].split(',') if b.strip()).most_common(20)),
            "topCategories": dict(Counter(c for x in records for c in set(x["categories"])).most_common(20))}


def sample(records, limit=100):
    buckets = [[r for r in records if r["quality"]["status"] == status] for status in ["passes_preliminary_checks", "needs_review", "incomplete"]]
    for bucket in buckets:
        bucket.sort(key=lambda r: hashlib.sha256(r["id"].encode()).hexdigest())
    result = []
    while len(result) < limit and any(buckets):
        for bucket in buckets:
            if bucket and len(result) < limit:
                result.append(bucket.pop())
    return result
