import copy
import importlib.util
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from validate import validate

class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.product = {"code":"4006381333931","rev":2,"countries_tags":["en:czech-republic"],"nutrition_data":"on","nutrition_data_per":"100g","nutriments":{}}
        vals={"kcal":57,"proteinG":5,"carbsG":7,"fatG":1,"sugarsG":4,"saturatedFatG":.5,"fiberG":None,"saltG":.1}
        for k,f in [("kcal","energy-kcal"),("proteinG","proteins"),("carbsG","carbohydrates"),("fatG","fat"),("sugarsG","sugars"),("saturatedFatG","saturated-fat"),("fiberG","fiber"),("saltG","salt")]:
            if vals[k] is not None:
                self.product["nutriments"].update({f+"_100g":vals[k],f+"_unit":"kcal" if k=="kcal" else "g"})
        self.imported={"id":"off:4006381333931","sourceID":"4006381333931","gtin14":"04006381333931","nutrition":{"basis":{"amount":100,"unit":"g"},"values":vals},"quality":{"status":"passes_preliminary_checks"}}
    def check(self):
        return validate(self.imported,{"product":self.product},"2026-10-18T21:00:00Z","live_api")
    def test_consistent_unverified_food_is_eligible_and_unknown_fibre_stays_null(self):
        r=self.check();self.assertTrue(r["eligible"]);self.assertEqual(r["verification"],"unverified");self.assertIsNone(r["nutrition"]["values"]["fiberG"])
    def test_qualified_core_value_never_becomes_zero_or_exact_bound(self):
        self.product["nutriments"]["fat_modifier"]="<";self.product["nutriments"]["fat_100g"]=.5
        r=self.check();self.assertFalse(r["eligible"]);self.assertIsNone(r["nutrition"]["values"]["fatG"]);self.assertEqual(r["nutrition"]["qualifiers"]["fatG"]["value"],.5)
    def test_missing_core_and_real_zero_are_distinct(self):
        del self.product["nutriments"]["fat_100g"]
        self.assertIn("core_nutrition_incomplete",self.check()["issues"])
        self.product["nutriments"]["fat_100g"]=0;self.imported["nutrition"]["values"]["fatG"]=0
        self.assertEqual(self.check()["nutrition"]["values"]["fatG"],0)
    def test_volume_pack_does_not_imply_density(self):
        self.product["product_quantity_unit"]="ml";r=self.check();self.assertIsNone(r["nutrition"]["basis"]["unit"]);self.assertFalse(r["eligible"])
    def test_explicit_millilitres_are_preserved(self):
        self.product["nutrition_data_per"]="100ml";self.product["quantity"]="500 ml"
        self.imported["nutrition"]["basis"]["unit"]="ml"
        self.assertTrue(self.check()["eligible"]);self.assertEqual(self.check()["nutrition"]["basis"]["unit"],"ml")
    def test_optional_qualifier_is_visible_even_if_import_was_missing(self):
        self.imported["nutrition"]["values"]["saltG"]=None
        self.product["nutriments"]["salt_modifier"]="~"
        r=self.check();self.assertFalse(r["eligible"]);self.assertIn("qualified_optional_nutrient:saltG",r["issues"])
        self.assertIsNone(r["nutrition"]["values"]["saltG"])
    def test_prepared_or_serving_basis_is_not_assumed_as_sold(self):
        self.product["nutrition_data_per"]="serving";self.assertFalse(self.check()["eligible"])
        self.product["nutrition_data_per"]="100g";self.product["nutrition_data"]="";self.product["nutrition_data_prepared"]="on"
        self.assertIn("as_sold_nutrition_unconfirmed",self.check()["issues"])
    def test_wrong_barcode_and_unknown_units_are_blocked(self):
        self.product["code"]="96385074";self.assertIn("barcode_mismatch_or_invalid",self.check()["issues"])
        self.product["nutriments"]["proteins_unit"]="oz";self.assertIn("unit_needs_review:proteinG",self.check()["issues"])
    def test_changed_source_nutrition_needs_review(self):
        self.product["nutriments"]["carbohydrates_100g"]=8;r=self.check();self.assertIn("nutrition_changed_since_import",r["issues"]);self.assertEqual(r["changes"][0]["imported"],7)
    def test_energy_conversion_and_kj_qualifier(self):
        n=self.product["nutriments"];del n["energy-kcal_100g"];n["energy-kj_100g"]=57*4.184;n["energy-kj_unit"]="kJ"
        self.assertTrue(self.check()["eligible"])
        n["energy-kj_modifier"]="<";self.assertFalse(self.check()["eligible"]);self.assertIsNone(self.check()["nutrition"]["values"]["kcal"])
    def test_source_failure_has_no_eligibility(self):
        r=validate(self.imported,{"status":"unavailable"},"2026-10-18T21:00:00Z","live_api");self.assertFalse(r["eligible"]);self.assertEqual(r["issues"],["source_unavailable"])

if __name__ == "__main__": unittest.main()
