"""OFF-only exception routing. No private search history or accounts in exports."""
import re
import math
from normalize import digest


def label_photos(product):
    code = str(product.get("code", ""))
    if not re.fullmatch(r"\d{8,14}", code):
        return []
    images = product.get("images") or {}
    if not isinstance(images, dict):
        return []
    selected = (images.get("selected") or {}).get("nutrition") or {}
    # Retain compatibility with OFF's older flat image representation.
    if not selected:
        selected = {k.removeprefix("nutrition_"): v for k, v in images.items() if re.fullmatch(r"nutrition_[a-z]{2}", k)}
    uploaded = images.get("uploaded") or images
    path = "/".join([code[:3], code[3:6], code[6:9], code[9:]]) if len(code) > 8 else code
    photos = []
    for lang, image in sorted(selected.items(), key=lambda pair: (pair[0] not in ("cs", "en"), pair[0] != "cs", pair[0])):
        if not re.fullmatch(r"[a-z]{2}", lang) or not isinstance(image, dict):
            continue
        revision = str(image.get("rev", ""))
        if not revision.isdigit():
            continue
        original = uploaded.get(str(image.get("imgid")), {})
        photos.append({"url": f"https://images.openfoodfacts.org/images/products/{path}/nutrition_{lang}.{revision}.full.jpg",
                       "imageKey": "nutrition_" + lang, "revision": revision, "originalImageID": image.get("imgid"),
                       "credit": original.get("uploader") or "Open Food Facts contributors", "license": "CC-BY-SA-3.0",
                       "sourceURL": f"https://world.openfoodfacts.org/product/{code}", "modifiedByLionne": False})
    return photos[:2]


def review_group(validation):
    if validation["eligible"]:
        return "available"
    issues = validation["issues"]
    if any(x in issues for x in ("barcode_mismatch_or_invalid", "source_revision_missing", "obsolete_or_no_nutrition", "source_not_found", "source_unavailable", "czech_country_tag_missing")):
        return "identity"
    if not validation.get("labelPhotos"):
        return "needs_photo"
    if any(x in issues for x in ("nutrition_changed_since_import", "energy_needs_review", "mass_sum_needs_review", "upstream_quality_error", "conflicting_gtin_aliases", "macro_out_of_range", "energy_out_of_range")):
        return "conflicts"
    return "label_needed"


def apply_accepted_review(validation, item):
    """Trusted admin export -> new snapshot; never overwrite upstream evidence.

    The caller must publish the OFF-only correction contents with the method.
    Human acceptance does not claim laboratory/human verification of the food.
    """
    v, r = validation, item.get("result") or {}
    if item.get("status") != "accepted" or item.get("sourceID") != v["sourceID"] or item.get("validation", {}).get("sourceSHA256") != v["sourceSHA256"]:
        raise ValueError("Stale or unaccepted OFF correction")
    if v["reviewGroup"] == "identity" or not r.get("canAccept") or r.get("issues") or r.get("warnings"):
        raise ValueError("Unresolved OFF correction")
    n = r.get("candidate", {}).get("nutrition") or {}
    if n.get("basis", {}).get("amount") != 100 or n["basis"].get("unit") not in ("g", "ml") or n.get("preparation") != "as_sold" or n.get("qualifiers"):
        raise ValueError("Correction basis/qualifiers require review")
    values = n.get("values") or {}
    core = ("kcal", "proteinG", "carbsG", "fatG")
    for key in core:
        value = values.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= (950 if key == "kcal" else 100):
            raise ValueError("Correction nutrient is invalid")
        if not (r.get("transcription", {}).get(key) or {}).get("quote"):
            raise ValueError("Correction has no label evidence")
    if n["basis"]["unit"] == "g" and sum(values[k] for k in core[1:]) > 105:
        raise ValueError("Correction mass exceeds basis")
    energy = 4 * values["proteinG"] + 4 * values["carbsG"] + 9 * values["fatG"]
    if abs(values["kcal"] - energy) > max(20, values["kcal"] * .15):
        raise ValueError("Correction energy needs review")
    if "product_name_missing" in v["issues"] and not r.get("candidate", {}).get("name", "").strip():
        raise ValueError("Correction name is missing")
    if not r.get("photos") or any(not re.fullmatch(r"[a-f0-9]{64}", p.get("sha256", "")) for p in r["photos"]):
        raise ValueError("Correction image evidence is missing")
    v["acceptedReview"] = {"sha256": digest(item), "previousNutrition": v["nutrition"], "previousIssues": v["issues"], "result": r}
    # Optional values are not carried across a corrected core/basis: they could
    # belong to another column, preparation, or product revision.
    v["nutrition"] = {"basis": n["basis"], "preparation": "as_sold", "values": {**{k: None for k in v["nutrition"]["values"]}, **{k: values[k] for k in core}}, "qualifiers": {}, "nutrientSources": {k: {"source": "off_label_review", "reviewSHA256": digest(item)} for k in core}}
    v["issues"], v["eligible"], v["reviewGroup"] = [], True, "available"
    v["warnings"] = ["accepted_label_correction_unverified"]
    return v
