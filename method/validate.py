"""OFF-only validation against the full JSON representation, including modifiers.

No private foods or users enter this module. Eligibility is an automated check,
never a human verification. An upstream nutrition change requires review.
"""
import hashlib
import json
import math
import re
from collections import Counter
from normalize import canonical, digest, gtin, number

RULES = "off-calculation-1"
FIELDS = {"kcal": "energy-kcal", "proteinG": "proteins", "carbsG": "carbohydrates", "fatG": "fat", "sugarsG": "sugars", "saturatedFatG": "saturated-fat", "fiberG": "fiber", "saltG": "salt"}
CORE = ("kcal", "proteinG", "carbsG", "fatG")
SOURCE_FIELDS = ["code", "rev", "last_modified_t", "product_name", "product_name_cs", "product_name_en", "brands", "quantity", "product_quantity_unit", "nutrition_data", "nutrition_data_per", "nutrition_data_prepared", "nutrition_data_prepared_per", "no_nutrition_data", "obsolete", "countries_tags", "categories_tags", "data_quality_errors_tags", "nutriments", "serving_size", "serving_quantity", "serving_quantity_unit"]


def project_evidence(p):
    return {k: p[k] for k in SOURCE_FIELDS if k in p}


def pilot(records):
    result = []
    for status, count in [("passes_preliminary_checks", 100), ("needs_review", 25), ("incomplete", 25)]:
        rows = sorted((r for r in records if r["quality"]["status"] == status), key=lambda r: hashlib.sha256(r["id"].encode()).hexdigest())
        result.extend(rows[:count])
    return result


def truth(v):
    return v is True or v == 1 or str(v).lower() in ("on", "true", "yes")


def validate(imported, evidence, checked_at, method):
    p = evidence.get("product")
    issues, changes, qualifiers = [], [], {}
    values = {k: None for k in FIELDS}
    unit = None
    if not p:
        issues.append("source_not_found" if evidence.get("status") == "not_found" else "source_unavailable")
    else:
        p = project_evidence(p)
        code = str(p.get("code", ""))
        if code != imported["sourceID"] or gtin(code) != imported["gtin14"] or not gtin(code):
            issues.append("barcode_mismatch_or_invalid")
        if not isinstance(p.get("rev"), int) or p["rev"] < 1:
            issues.append("source_revision_missing")
        if truth(p.get("obsolete")) or truth(p.get("no_nutrition_data")):
            issues.append("obsolete_or_no_nutrition")
        if "en:czech-republic" not in (p.get("countries_tags") or []):
            issues.append("czech_country_tag_missing")
        if p.get("data_quality_errors_tags"):
            issues.append("upstream_quality_error")
        per = p.get("nutrition_data_per")
        unit = "g" if per == "100g" else "ml" if per == "100ml" else None
        volume_hint = (p.get("product_quantity_unit") in ("ml", "cl", "dl", "l")
                       or p.get("serving_quantity_unit") in ("ml", "cl", "dl", "l")
                       or re.search(r"\d\s*(?:ml|cl|dl|l|litres?|liters?)\b", str(p.get("quantity", "")), re.I)
                       or bool(set(p.get("categories_tags") or []) & {"en:beverages", "en:milks", "en:plant-based-milks"}))
        if unit == "g" and volume_hint:
            unit = None
        if unit is None:
            issues.append("nutrition_basis_needs_label")
        if p.get("nutrition_data") not in ("on", True, 1):
            issues.append("as_sold_nutrition_unconfirmed")
        n = p.get("nutriments") or {}
        for key, field in FIELDS.items():
            value = number(n.get(field + "_100g"))
            modifier = n.get(field + "_modifier")
            input_unit = n.get(field + "_unit")
            allowed = ("kcal",) if key == "kcal" else ("g", "mg", "µg", "μg", "mcg")
            if value is not None and input_unit not in allowed:
                issues.append("unit_needs_review:" + key)
            if modifier not in (None, "", "="):
                qualifiers[key] = {"operator": modifier, "value": value, "reportedValue": n.get(field + "_value"), "reportedUnit": input_unit}
                value = None
                if key in CORE:
                    issues.append("qualified_core_nutrient:" + key)
                else:
                    issues.append("qualified_optional_nutrient:" + key)
            if key == "kcal" and value is None and not modifier and number(n.get("energy-kj_100g")) is not None:
                if n.get("energy-kj_modifier") not in (None, "", "="):
                    qualifiers[key] = {"operator": n["energy-kj_modifier"], "value": number(n["energy-kj_100g"]) / 4.184, "reportedUnit": "kJ"}
                    issues.append("qualified_core_nutrient:kcal")
                elif n.get("energy-kj_unit") == "kJ":
                    value = number(n["energy-kj_100g"]) / 4.184
                else:
                    issues.append("unit_needs_review:kcal")
            values[key] = value
            old = imported["nutrition"]["values"].get(key)
            if old != value and not (old is not None and value is not None and math.isclose(old, value, rel_tol=1e-7, abs_tol=1e-6)):
                changes.append({"field": key, "imported": old, "current": value})
        if unit != imported["nutrition"]["basis"]["unit"]:
            changes.append({"field": "basis", "imported": imported["nutrition"]["basis"]["unit"], "current": unit})
        if changes:
            issues.append("nutrition_changed_since_import")
        if any(values[k] is None for k in CORE):
            issues.append("core_nutrition_incomplete")
        if values["kcal"] is not None and values["kcal"] > 950:
            issues.append("energy_out_of_range")
        if any(values[k] is not None and values[k] > 100 for k in CORE[1:]):
            issues.append("macro_out_of_range")
        for child, parent in [("sugarsG", "carbsG"), ("saturatedFatG", "fatG")]:
            if values[child] is not None and values[parent] is not None and values[child] > values[parent] + .5:
                issues.append(child + "_exceeds_" + parent)
        if unit == "g" and all(values[k] is not None for k in CORE[1:]) and sum(values[k] for k in CORE[1:]) + (values["fiberG"] or 0) + (values["saltG"] or 0) > 105:
            issues.append("mass_sum_needs_review")
        if all(values[k] is not None for k in CORE):
            energy = 4 * values["proteinG"] + 4 * values["carbsG"] + 9 * values["fatG"] + 2 * (values["fiberG"] or 0)
            if abs(values["kcal"] - energy) > max(20, .15 * values["kcal"]):
                issues.append("energy_needs_review")
    if imported["quality"]["status"] != "passes_preliminary_checks":
        issues.append("preliminary_review_required")
    source_hash = digest(p) if p else None
    return {"id": imported["id"], "sourceID": imported["sourceID"], "gtin14": imported["gtin14"], "rulesVersion": RULES,
            "eligible": not issues, "verification": "unverified", "checkedAt": checked_at, "method": method,
            "sourceRevision": p.get("rev") if p else None, "sourceLastModifiedUnix": p.get("last_modified_t") if p else None,
            "sourceSHA256": source_hash, "importSHA256": digest(imported), "issues": sorted(set(issues)), "changes": changes,
            "nutrition": {"basis": {"amount": 100, "unit": unit}, "preparation": "as_sold", "values": values, "qualifiers": qualifiers}}


def report(rows):
    return {"total": len(rows), "eligible": sum(r["eligible"] for r in rows), "needsReview": sum(not r["eligible"] for r in rows),
            "issues": dict(Counter(i for r in rows for i in r["issues"]).most_common()), "changed": sum(bool(r["changes"]) for r in rows)}
