from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.contrib.staticfiles.storage import staticfiles_storage
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .forms import LibraryFieldForm
from .matrix import (
    convert_base_values, empty_values, fingerprint, legacy_definition,
    normalize_definition, normalize_value, validate_values,
)
from .models import Assignment, AssignmentSubmission, Case, Education, LibraryDossier, LibraryDossierModule, LibraryField, LibraryTemplate, Module, ModuleField, Patient, Profile, StudentCase, TeachingGroup
from .module_data import parse_module_form
from .services import copy_library_dossier_to_case, copy_template_to_case, start_student_case


def sheet():
    definition = legacy_definition(["Metingen", "Controle"], ["Omschrijving", "Waarde", "Akkoord"])
    definition["cells"] = {
        "r0": {"c0": {"type": "label", "text": "Temperatuur"}, "c1": {"type": "number", "required": True, "min": "30", "max": "45", "unit": "°C"}, "c2": {"type": "checkbox", "required": True}},
        "r1": {"c0": {"type": "text", "read_only": True, "default": "Vooraf ingevuld"}, "c1": {"type": "select", "options": ["Ja", "Nee"]}, "c2": {"type": "multiselect", "options": ["A", "B", "C"]}},
    }
    return definition


def values():
    return {"version": 2, "cells": {"r0": {"c1": "36,75", "c2": False}, "r1": {"c0": "Vooraf ingevuld", "c1": "Nee", "c2": ["A", "C"]}}}


class MatrixContractTests(SimpleTestCase):
    def test_matrix_assets_collect_with_production_manifest_storage(self):
        with TemporaryDirectory() as directory, override_settings(
            STATIC_ROOT=directory,
            STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}},
        ):
            call_command("collectstatic", interactive=False, verbosity=0)
            for filename in ("matrix-editor.js", "matrix-core.mjs", "matrix.css"):
                self.assertTrue((Path(directory) / filename).is_file())
                self.assertTrue((Path(directory) / staticfiles_storage.stored_name(filename)).is_file())

    def test_mixed_values_preserve_precision_false_and_options(self):
        normalized, errors, filled = validate_values(sheet(), values(), complete=True, current=empty_values())
        self.assertFalse(errors)
        self.assertTrue(filled)
        self.assertEqual(normalized["cells"]["r0"]["c1"], "36.75")
        self.assertIs(normalized["cells"]["r0"]["c2"], False)
        self.assertEqual(normalize_value("00012", {"type": "text"}), "00012")
        self.assertEqual(normalize_value("12345678901234567890,123456789", {"type": "number"}), "12345678901234567890.123456789")

    def test_entered_values_validated_but_missing_required_only_on_submit(self):
        _, errors, _ = validate_values(sheet(), empty_values())
        self.assertFalse(errors)
        _, errors, filled = validate_values(sheet(), empty_values(), complete=True)
        self.assertEqual(len(errors), 2)
        self.assertFalse(filled)  # Fixed labels and readonly defaults do not count as answers.
        self.assertIn("Rij 1 (Metingen), kolom 2 (Waarde)", errors[0])

    def test_type_rules_and_exact_numeric_bounds(self):
        for value, spec in [
            ("NaN", {"type": "number"}), ("1.234,56", {"type": "number"}),
            ("0.10000000000000000001", {"type": "number", "max": "0.1"}),
            ("2026-02-30", {"type": "date"}), ("2026-10-15T12:00+02:00", {"type": "datetime"}),
            ("25:00", {"type": "time"}), ("true", {"type": "boolean"}),
            (["Z"], {"type": "multiselect", "options": ["A"]}), ("ABC", {"max_length": 2}),
        ]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                normalize_value(value, spec)
        for kind, value in [("date", "2024-02-29"), ("time", "23:59:59"), ("datetime", "2026-10-15T12:45"), ("boolean", False), ("number", "0")]:
            self.assertEqual(normalize_value(value, {"type": kind, "required": True}, complete=True), value)

    def test_schema_rejects_unsafe_or_unbounded_metadata(self):
        mutations = [
            lambda s: s["rows"].append(deepcopy(s["rows"][0])),
            lambda s: s["columns"][0].update(id="__proto__"),
            lambda s: s["rows"][0].update(height=99999),
            lambda s: s["cells"]["r0"]["c1"].update(type=[]),
            lambda s: s["cells"]["r0"]["c1"].update(style={"background": "url(https://example.org)"}),
            lambda s: s["cells"]["r0"]["c1"].update(formula="=A1"),
            lambda s: s["cells"]["r1"]["c1"].update(options=[]),
            lambda s: s["cells"]["r0"]["c1"].update(min="50", max="40"),
            lambda s: s["cells"]["r0"]["c1"].update(default="geen getal"),
            lambda s: s.update(rows=[{"id": f"r{i}", "label": ""} for i in range(101)]),
        ]
        for mutate in mutations:
            definition = sheet(); mutate(definition)
            with self.subTest(definition=definition), self.assertRaises(ValidationError):
                normalize_definition(definition)
        self.assertEqual(normalize_definition(sheet()), sheet())

    def test_unknown_and_protected_cells_rejected(self):
        for row, col, value in [("unknown", "c1", "x"), ("r0", "unknown", "x"), ("r0", "c0", "Vervalsing"), ("r1", "c0", "Wijziging")]:
            payload = values(); payload["cells"].setdefault(row, {})[col] = value
            self.assertTrue(validate_values(sheet(), payload, current=empty_values())[1])

    def test_malformed_payloads_fail_without_exceptions(self):
        for payload in [None, [], "x", {}, {"version": 2, "cells": []}, {"version": 2, "cells": {"r0": []}}]:
            self.assertTrue(validate_values(sheet(), payload)[1])
        schema = [{"key": "matrix", "type": "matrix", "matrix_definition": sheet()}]
        self.assertTrue(parse_module_form({"matrix_matrix": "{"}, schema, {}).errors)

    def test_parse_preserves_invalid_cells_and_other_fields(self):
        payload = values(); payload["cells"]["r0"]["c1"] = "36,"
        schema = [{"key": "matrix", "type": "matrix", "matrix_definition": sheet()}, {"key": "other", "type": "short_text"}]
        payload["cells"]["r0"]["c1"] = "<ongeldig>"
        result = parse_module_form({"matrix_matrix": json.dumps(payload), "field_other": " Nog niet bewaard "}, schema, {})
        self.assertTrue(result.errors)
        self.assertEqual(result.display_data["matrix"], payload)
        self.assertEqual(result.display_data["other"], " Nog niet bewaard ")

    def test_legacy_conversion_preserves_ids_after_reordering_and_rejects_loss(self):
        old = {"rows": ["Eerste", "Tweede"], "columns": ["Waarde"]}
        definition = legacy_definition(old["rows"], old["columns"])
        definition["rows"].reverse()
        result = convert_base_values(old, definition, {"0_0": "0012", "1_0": "0"})
        self.assertEqual(result["cells"], {"r1": {"c0": "0"}, "r0": {"c0": "0012"}})
        definition["rows"].pop()
        with self.assertRaises(ValidationError):
            convert_base_values(old, definition, {"0_0": "behouden"})
        with self.assertRaises(ValidationError):
            convert_base_values(old, definition, {"9_9": "onbekend"})


@override_settings(SECURE_SSL_REDIRECT=False)
class MatrixWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.teacher = users.objects.create_user("matrix-teacher")
        cls.teacher.epd_profile.role = Profile.Role.TEACHER
        cls.teacher.epd_profile.save()
        cls.admin = users.objects.create_superuser("matrix-admin")
        cls.student = users.objects.create_user("matrix-student")
        cls.other = users.objects.create_user("matrix-other")
        cls.education = Education.objects.get(slug="vroedkunde")
        cls.case = Case.objects.create(title="Matrixcasus", patient=Patient.objects.create(name="Fictieve matrix", reference="MATRIX-TEST"), education=cls.education, created_by=cls.teacher, status=Case.Status.PUBLISHED)
        cls.group = TeachingGroup.objects.create(name="Matrixgroep", education=cls.education, teacher=cls.teacher)
        cls.group.members.add(cls.student, cls.other); cls.case.allowed_groups.add(cls.group)
        Assignment.objects.create(case=cls.case, title="Controleer")
        cls.template = LibraryTemplate.objects.create(title="Matrixmodule", category=LibraryTemplate.Category.MODULE, education=cls.education, created_by=cls.teacher)
        cls.field = LibraryField.objects.create(template=cls.template, key="sheet", label="Flexibele matrix", field_type="matrix", matrix_definition=sheet(), required=True)
        cls.module = copy_template_to_case(cls.template, cls.case)
        ModuleField.objects.create(module=cls.module, key="other", label="Andere invoer", field_type="short_text")
        ModuleField.objects.create(module=cls.module, key="obs", label="Observatie", field_type="observation")
        cls.student_case, _ = start_student_case(cls.case, cls.student)
        cls.response = cls.student_case.module_responses.get(module=cls.module)
        cls.other_case, _ = start_student_case(cls.case, cls.other)
        cls.url = reverse("dossier:dossier", args=[cls.case.pk])
        cls.base_url = reverse("dossier:teacher_module", args=[cls.case.pk, cls.module.pk])
        cls.field_url = reverse("dossier:library_field_edit", args=[cls.template.pk, cls.field.pk])

    def post_data(self, payload=None, **extra):
        return {"module": self.response.pk, "matrix_sheet": json.dumps(values() if payload is None else payload), "field_other": "Ook bewaren", "action": "save", **extra}

    def edit_data(self, field=None, definition=None):
        field = field or self.field
        return {"label": field.label, "field_type": "matrix", "position": 0, "required": "on", "matrix_definition": json.dumps(definition or sheet()), "revision": fingerprint(field)}

    def test_template_and_dossier_bundle_copy_include_matrix_definition(self):
        self.assertEqual(self.module.fields.get(key="sheet").matrix_definition, sheet())
        new_case = Case.objects.create(title="Sjabloonkopie", education=self.education, patient=Patient.objects.create(name="Fictief", reference="MATRIX-BUNDLE"), created_by=self.teacher)
        dossier = LibraryDossier.objects.create(title="Matrixsjabloon", education=self.education, created_by=self.teacher)
        LibraryDossierModule.objects.create(dossier=dossier, template=self.template, position=0)
        self.assertFalse(new_case.modules.exists())
        copied = copy_library_dossier_to_case(dossier, new_case)[0]
        self.assertEqual(copied.fields.get(key="sheet").matrix_definition, sheet())
        self.assertEqual(copy_library_dossier_to_case(dossier, new_case)[0].pk, copied.pk)
        student_case, _ = start_student_case(new_case, self.other)
        self.assertEqual(student_case.module_responses.get().schema[0]["matrix_definition"], sheet())

    def test_two_student_snapshots_remain_independent_after_source_changes(self):
        self.module.fields.filter(key="sheet").update(matrix_definition=legacy_definition(["Nieuw"], ["Nieuw"]))
        self.field.matrix_definition = legacy_definition(["Bron"], ["Bron"]); self.field.save()
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(self.url, self.post_data()).status_code, 302)
        self.response.refresh_from_db()
        self.assertEqual(self.response.schema[0]["matrix_definition"], sheet())
        other = self.other_case.module_responses.get(module=self.module)
        self.assertEqual(other.schema[0]["matrix_definition"], sheet())
        self.assertEqual(other.data, {})

    def test_both_editors_save_matrix_other_fields_and_observation_together(self):
        for user, url, record, attribute in [(self.student, self.url, self.response, "data"), (self.teacher, self.base_url, self.module, "base_data")]:
            self.client.force_login(user)
            result = self.client.post(url, self.post_data(action="add_observation:obs", observation_timestamp_obs="2026-10-15T12:00", observation_value_obs="Controle", observation_note_obs="Notitie"))
            self.assertEqual(result.status_code, 302)
            record.refresh_from_db(); data = getattr(record, attribute)
            self.assertEqual(data["sheet"]["cells"]["r0"]["c1"], "36.75")
            self.assertEqual(data["other"], "Ook bewaren")
            self.assertEqual(len(data["obs"]), 1)

    def test_invalid_matrix_preserves_raw_input_and_does_not_partially_save(self):
        payload = values(); payload["cells"]["r0"]["c1"] = "<script>fout</script>"
        for user, url in [(self.student, self.url), (self.teacher, self.base_url)]:
            self.client.force_login(user)
            result = self.client.post(url, self.post_data(payload, observation_timestamp_obs="2026-10-15T12:00", observation_value_obs="Nog niet bewaard"))
            self.assertEqual(result.status_code, 200)
            field = next(field for field in result.context["fields"] if field["key"] == "sheet")
            self.assertEqual(field["matrix_payload"]["values"], payload)
            self.assertContains(result, "Ook bewaren")
            self.assertContains(result, "Nog niet bewaard")
            self.assertNotContains(result, "<script>fout</script>")
        self.response.refresh_from_db(); self.module.refresh_from_db()
        self.assertEqual(self.response.data, {}); self.assertEqual(self.module.base_data, {})

    def test_final_submission_requires_specific_cells_and_accepts_false(self):
        self.client.force_login(self.student)
        self.student_case.assignment_submissions.update(status=AssignmentSubmission.Status.SUBMITTED)
        submit = reverse("dossier:submit_student_case", args=[self.case.pk])
        self.assertEqual(self.client.post(self.url, self.post_data(empty_values())).status_code, 302)
        result = self.client.post(submit, follow=True)
        self.assertContains(result, "Deze cel is verplicht")
        self.student_case.refresh_from_db(); self.assertEqual(self.student_case.status, StudentCase.Status.ACTIVE)
        self.assertEqual(self.client.post(self.url, self.post_data()).status_code, 302)
        self.assertEqual(self.client.post(submit).status_code, 302)
        self.student_case.refresh_from_db(); self.assertEqual(self.student_case.status, StudentCase.Status.SUBMITTED)
        result = self.client.post(self.url, self.post_data(field_other="Mag niet veranderen"))
        self.assertEqual(result.status_code, 302)
        self.response.refresh_from_db(); self.assertEqual(self.response.data["other"], "Ook bewaren")

    def test_protected_cells_cannot_be_changed_by_student_but_teacher_can_prefill(self):
        payload = values(); payload["cells"]["r1"]["c0"] = "Docentvoorinvulling"
        self.client.force_login(self.student)
        result = self.client.post(self.url, self.post_data(payload))
        self.assertContains(result, "alleen-lezen")
        self.response.refresh_from_db(); self.assertEqual(self.response.data, {})
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.post(self.base_url, self.post_data(payload)).status_code, 302)
        self.module.refresh_from_db(); self.assertEqual(self.module.base_data["sheet"]["cells"]["r1"]["c0"], "Docentvoorinvulling")

    def test_teacher_updates_existing_matrix_without_flattening_or_changing_student_copy(self):
        self.module.base_data = {"sheet": values(), "other": "Bestaande tekst"}
        self.module.save()
        self.client.force_login(self.teacher)
        changed = values()
        changed["cells"]["r0"]["c1"] = "37,2"
        self.assertEqual(self.client.post(self.base_url, self.post_data(changed)).status_code, 302)
        self.module.refresh_from_db()
        self.assertEqual(self.module.base_data["sheet"]["version"], 2)
        self.assertEqual(self.module.base_data["sheet"]["cells"]["r0"]["c1"], "37.2")
        self.assertNotIn("0_0", self.module.base_data["sheet"])
        # A partial POST must retain the saved matrix when no new payload is sent.
        self.assertEqual(self.client.post(self.base_url, {
            "action": "save", "field_other": "Alleen tekst gewijzigd",
        }).status_code, 302)
        self.module.refresh_from_db()
        self.assertEqual(self.module.base_data["sheet"]["cells"]["r0"]["c1"], "37.2")
        self.response.refresh_from_db()
        self.assertEqual(self.response.data, {})

    def test_review_has_readable_grid_and_no_editable_payload(self):
        self.response.data = {"sheet": values()}; self.response.save()
        self.client.force_login(self.teacher)
        result = self.client.get(reverse("dossier:teacher_student_case", args=[self.student_case.pk]))
        self.assertContains(result, 'data-readonly="true"')
        self.assertContains(result, "Temperatuur")
        self.assertContains(result, "A; C")
        self.assertNotContains(result, '<input type="hidden" name="matrix_sheet"')

    def test_matrix_and_rich_text_save_together_and_survive_validation_errors(self):
        rich_field = ModuleField.objects.create(
            module=self.module, key="rich", label="Opgemaakte toelichting", field_type="rich_text"
        )
        self.response.schema.append(rich_field.as_schema())
        self.response.save()
        self.client.force_login(self.student)
        rich_text = "<p><strong>Toelichting</strong> bij de meting</p>"
        self.assertEqual(self.client.post(self.url, self.post_data(field_rich=rich_text)).status_code, 302)
        self.response.refresh_from_db()
        self.assertEqual(self.response.data["rich"], rich_text)
        self.assertEqual(self.response.data["sheet"]["cells"]["r0"]["c1"], "36.75")
        invalid = values()
        invalid["cells"]["r0"]["c1"] = "geen getal"
        result = self.client.post(self.url, self.post_data(invalid, field_rich="<p>Nieuwe tekst</p>"))
        self.assertContains(result, 'class="js-tinymce"')
        self.assertContains(result, "&lt;p&gt;Nieuwe tekst&lt;/p&gt;")
        self.assertEqual(result.context["fields"][0]["matrix_payload"]["values"], invalid)
        self.response.refresh_from_db()
        self.assertEqual(self.response.data["rich"], rich_text)

    def test_review_combines_matrix_rich_text_and_prefilled_assignment_feedback(self):
        rich_schema = {"key": "rich", "label": "Toelichting", "type": "rich_text"}
        self.response.schema.append(rich_schema)
        self.response.data = {
            "sheet": values(), "other": "<strong>Gewone tekst</strong>",
            "rich": '<p><strong>Opgemaakt</strong><script>alert(1)</script></p>',
        }
        self.response.save()
        submission = self.student_case.assignment_submissions.get()
        submission.answer = "Antwoord voor feedback"
        submission.status = "submitted"
        submission.save()
        self.client.force_login(self.teacher)
        result = self.client.get(reverse("dossier:teacher_student_case", args=[self.student_case.pk]))
        self.assertContains(result, 'data-readonly="true"')
        self.assertContains(result, "<strong>Opgemaakt</strong>", html=True)
        self.assertContains(result, "&lt;strong&gt;Gewone tekst&lt;/strong&gt;")
        self.assertNotContains(result, "<script>alert(1)</script>")
        # Read from the prefetched instances that the view decorated.
        displayed_submission = list(result.context["student_case"].assignment_submissions.all())[0]
        # Bij de eerste beoordeling is het feedbackveld leeg; de
        # studentantwoord wordt alleen overgenomen via de knop.
        self.assertEqual(displayed_submission.review_form.initial["feedback"], submission.feedback)
        self.assertContains(result, "Antwoord voor feedback")
        self.assertContains(result, 'name="status"')
        self.assertContains(result, 'name="feedback"')
        # Voor de eerste beoordeling bestaat er nog geen "vorige beoordeling".
        self.assertNotContains(result, "Vorige beoordeling")
        reviewed = self.client.post(reverse("dossier:teacher_review_assignment", args=[
            self.student_case.pk, submission.pk,
        ]), {"status": "approved", "feedback": "Correct beoordeeld"})
        self.assertEqual(reviewed.status_code, 302)
        submission.refresh_from_db()
        self.assertEqual(submission.status, AssignmentSubmission.Status.APPROVED)
        self.assertEqual(submission.feedback, "Correct beoordeeld")
        # Een al goedgekeurde opdracht kan weer naar "opnieuw inleveren".
        re_reviewed = self.client.post(reverse("dossier:teacher_review_assignment", args=[
            self.student_case.pk, submission.pk,
        ]), {"status": "resubmit", "feedback": "Niet goed genoeg, probeer het opnieuw"})
        self.assertEqual(re_reviewed.status_code, 302)
        submission.refresh_from_db()
        self.student_case.refresh_from_db()
        self.assertEqual(submission.status, AssignmentSubmission.Status.RESUBMIT)
        self.assertEqual(submission.feedback, "Niet goed genoeg, probeer het opnieuw")
        self.assertEqual(self.student_case.status, StudentCase.Status.ACTIVE)
        # En de herbeoordeling toont de eerdere feedback in het veld
        # én de vorige beoordeling leesbaar in een eigen box.
        result = self.client.get(reverse("dossier:teacher_student_case", args=[self.student_case.pk]))
        re_displayed = list(result.context["student_case"].assignment_submissions.all())[0]
        self.assertEqual(
            re_displayed.review_form.initial["feedback"], "Niet goed genoeg, probeer het opnieuw"
        )
        self.assertContains(result, "Vorige beoordeling: Opnieuw inleveren")
        self.assertContains(result, "Niet goed genoeg, probeer het opnieuw")

    def test_empty_required_flexible_matrix_can_be_prefilled_and_published(self):
        self.client.force_login(self.teacher)
        result = self.client.post(self.base_url, self.post_data(empty_values()), follow=True)
        self.assertContains(result, "Voorinvullen is optioneel.")
        self.module.refresh_from_db()
        self.assertEqual(self.module.base_data["sheet"]["cells"]["r0"]["c1"], "")
        self.case.move_to_draft()
        self.case.save()
        result = self.client.post(
            reverse("dossier:teacher_case_transition", args=[self.case.pk]), {"action": "publish"}, follow=True
        )
        self.assertContains(result, "Casus gepubliceerd voor studenten.")
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Case.Status.PUBLISHED)

    def test_stale_authoring_form_rejected_without_overwriting_new_version(self):
        self.client.force_login(self.teacher)
        payload = self.edit_data()
        self.field.label = "Nieuwere naam"; self.field.save()
        result = self.client.post(self.field_url, payload)
        self.assertContains(result, "intussen gewijzigd")
        self.field.refresh_from_db(); self.assertEqual(self.field.label, "Nieuwere naam")
        self.assertContains(result, "data-matrix-designer")

    def test_schema_editor_creates_new_grid_without_manual_row_lists(self):
        self.client.force_login(self.teacher)
        url = reverse("dossier:library_field_create", args=[self.template.pk])
        form = self.client.get(url).context["form"]
        payload = self.edit_data(); payload["revision"] = form.fields["revision"].initial; payload["label"] = "Nieuwe grid"
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        field = self.template.fields.get(label="Nieuwe grid")
        self.assertEqual(field.matrix_definition, sheet())
        self.assertEqual(field.rows, ["Metingen", "Controle"])

    def test_legacy_source_conversion_is_atomic_and_preserves_student_snapshot(self):
        field = self.module.fields.get(key="sheet")
        field.matrix_definition = {}; field.rows = ["Eerste", "Tweede"]; field.columns = ["Waarde"]; field.save()
        self.module.base_data = {"sheet": {"0_0": "0012", "1_0": ""}}; self.module.save()
        definition = legacy_definition(field.rows, field.columns); definition["rows"].reverse()
        self.client.force_login(self.admin)
        url = reverse("dossier:teacher_module_field_edit", args=[self.case.pk, self.module.pk, field.pk])
        self.assertEqual(self.client.post(url, self.edit_data(field, definition)).status_code, 302)
        self.module.refresh_from_db(); field.refresh_from_db()
        self.assertEqual(self.module.base_data["sheet"]["cells"]["r0"]["c0"], "0012")
        definition["rows"].pop()
        result = self.client.post(url, self.edit_data(field, definition))
        self.assertContains(result, "voorinvulling verwijderen")
        field.refresh_from_db(); self.module.refresh_from_db(); self.response.refresh_from_db()
        self.assertEqual(len(field.matrix_definition["rows"]), 2)
        self.assertEqual(self.module.base_data["sheet"]["cells"]["r0"]["c0"], "0012")
        self.assertEqual(self.response.schema[0]["matrix_definition"], sheet())

    def test_schema_validation_errors_keep_submitted_definition(self):
        invalid = sheet(); invalid["cells"]["r0"]["c1"]["default"] = "geen getal"
        form = LibraryFieldForm(data=self.edit_data(definition=invalid), instance=self.field, parent=self.template)
        self.assertFalse(form.is_valid())
        self.assertIn("matrix_definition", form.errors)
        self.assertIn("geen getal", form["matrix_definition"].value())

    def test_missing_payload_preserves_existing_values(self):
        self.response.data = {"sheet": values()}; self.response.save()
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(self.url, {"module": self.response.pk, "field_other": "Zonder JavaScript"}).status_code, 302)
        self.response.refresh_from_db()
        self.assertEqual(self.response.data["sheet"]["cells"]["r0"]["c1"], "36.75")

    def test_changing_field_type_cannot_discard_existing_prefill(self):
        field = self.module.fields.get(key="sheet")
        self.module.base_data = {"sheet": values()}; self.module.save()
        self.client.force_login(self.admin)
        url = reverse("dossier:teacher_module_field_edit", args=[self.case.pk, self.module.pk, field.pk])
        payload = self.edit_data(field); payload["field_type"] = "short_text"
        result = self.client.post(url, payload)
        self.assertContains(result, "voorinvulling eerst bewust leeg")
        field.refresh_from_db(); self.module.refresh_from_db()
        self.assertEqual(field.field_type, "matrix")
        self.assertEqual(self.module.base_data["sheet"], values())

    def test_oversized_valid_json_keeps_raw_answers_on_error(self):
        payload = values(); payload["cells"]["r1"]["c0"] = "X" * 512001
        schema = self.response.schema
        result = parse_module_form(self.post_data(payload), schema, {}, edit_readonly=True)
        self.assertTrue(result.errors)
        self.assertEqual(result.display_data["sheet"], payload)

    def test_required_matrix_cannot_be_designed_without_answer_cells(self):
        definition = legacy_definition(["Rij"], ["Kolom"])
        definition["cells"] = {"r0": {"c0": {"type": "label", "text": "Alleen een kop"}}}
        form = LibraryFieldForm(data=self.edit_data(definition=definition), instance=self.field, parent=self.template)
        self.assertFalse(form.is_valid())
        self.assertIn("required", form.errors)

    def test_changing_an_empty_prefilled_field_also_converts_its_value_container(self):
        field = self.module.fields.get(key="sheet")
        self.module.base_data = {"sheet": empty_values()}; self.module.save()
        self.client.force_login(self.admin)
        url = reverse("dossier:teacher_module_field_edit", args=[self.case.pk, self.module.pk, field.pk])
        payload = self.edit_data(field); payload["field_type"] = "short_text"
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        field.refresh_from_db(); self.module.refresh_from_db()
        self.assertEqual(self.module.base_data["sheet"], "")
        self.assertEqual(self.client.post(url, self.edit_data(field)).status_code, 302)
        self.module.refresh_from_db()
        self.assertEqual(self.module.base_data["sheet"], empty_values())

    def test_unauthorized_source_and_foreign_module_posts_are_rejected(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(self.field_url, self.edit_data()).status_code, 403)
        other_response = self.other_case.module_responses.get(module=self.module)
        self.assertEqual(self.client.post(self.url, self.post_data(module=other_response.pk)).status_code, 404)
        self.client.force_login(self.teacher)
        field = self.module.fields.get(key="sheet")
        url = reverse("dossier:teacher_module_field_edit", args=[self.case.pk, self.module.pk, field.pk])
        self.assertEqual(self.client.post(url, self.edit_data(field)).status_code, 403)
