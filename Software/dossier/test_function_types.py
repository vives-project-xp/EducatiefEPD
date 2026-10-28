from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from .function_types import FUNCTION_TYPES
from .views import prepare_function_forms


class FunctionTypeRenderingTests(SimpleTestCase):
    def snapshot(self, field_types):
        return SimpleNamespace(
            id=1,
            title="Voorbeeldfunctie",
            kind="formulier",
            definition={
                "forms": [{
                    "id": 2,
                    "title": "Voorbeeldformulier",
                    "questions": [
                        {
                            "id": index,
                            "fieldType": field_type,
                            "question": f"Vraag {field_type}",
                            "required": False,
                            "options": ["Een", "Twee"],
                            "rows": ["Rij"],
                            "columns": ["Kolom"],
                            "matrixDefinition": {},
                            "url": "https://example.com",
                            "buttonText": "Open",
                            "image": "",
                            "caption": "",
                            "explanation": "Uitleg",
                        }
                        for index, field_type in enumerate(field_types)
                    ],
                }]
            },
        )

    def render(self, field_types):
        forms = prepare_function_forms([self.snapshot(field_types)], {})
        return render_to_string(
            "dossier/_function_snapshots.html",
            {"function_forms": forms, "locked": False, "student_dossier": False},
        )

    def test_registry_contains_a_renderer_input_for_every_type(self):
        html = self.render([item.key for item in FUNCTION_TYPES])
        self.assertNotIn("Deze vraag kan niet worden weergegeven.", html)
        self.assertIn("type=\"file\"", html)
        self.assertIn("type=\"datetime-local\"", html)
        self.assertIn("observation-entry", html)
        self.assertIn("data-matrix", html)
        self.assertIn("function-information", html)

    def test_unknown_and_legacy_time_questions_do_not_crash(self):
        html = self.render(["time", "removed-type"])
        self.assertIn("type=\"time\"", html)
        self.assertIn("Deze vraag kan niet worden weergegeven.", html)

    def test_registry_does_not_offer_time(self):
        self.assertNotIn("time", [item.key for item in FUNCTION_TYPES])
        self.assertIn("observation", [item.key for item in FUNCTION_TYPES])
