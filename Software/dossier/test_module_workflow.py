from copy import deepcopy

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.html import escape

from .models import (
    Assignment, AssignmentSubmission, AuditEvent, Case, Education, Module,
    ModuleField, Patient, Profile, StudentCase, TeachingGroup,
)
from .services import start_student_case


@override_settings(SECURE_SSL_REDIRECT=False)
class ModuleWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.teacher = users.objects.create_user("workflow-teacher")
        cls.teacher.epd_profile.role = Profile.Role.TEACHER
        cls.teacher.epd_profile.save()
        cls.student = users.objects.create_user("workflow-student")
        cls.other_student = users.objects.create_user("workflow-other")
        education = Education.objects.get(slug="vroedkunde")
        patient = Patient.objects.create(name="Fictieve casus", reference="WORKFLOW-001")
        cls.case = Case.objects.create(
            title="Workflowtest", patient=patient, education=education,
            created_by=cls.teacher, status=Case.Status.PUBLISHED,
        )
        cls.group = TeachingGroup.objects.create(name="Workflowgroep", education=education, teacher=cls.teacher)
        cls.group.members.add(cls.student, cls.other_student)
        cls.case.allowed_groups.add(cls.group)
        Assignment.objects.create(case=cls.case, title="Opdracht")
        cls.module = Module.objects.create(case=cls.case, title="Gemengd formulier")
        definitions = [
            ("text", "short_text", {}), ("number", "number", {}),
            ("date", "date", {}), ("datetime", "datetime", {}),
            ("choice", "select", {"options": ["Ja", "Nee"]}),
            ("matrix", "matrix", {"rows": ["Rij 1", "Rij 2"], "columns": ["Kolom 1", "Kolom 2"]}),
            ("observations", "observation", {}),
        ]
        for position, (key, field_type, extra) in enumerate(definitions):
            ModuleField.objects.create(
                module=cls.module, label=f"Veld {key}", key=key,
                field_type=field_type, required=True, position=position, **extra,
            )
        cls.student_case, _ = start_student_case(cls.case, cls.student)
        cls.response = cls.student_case.module_responses.get()
        cls.submission = cls.student_case.assignment_submissions.get()
        cls.submission.status = AssignmentSubmission.Status.SUBMITTED
        cls.submission.save()
        cls.other_case, _ = start_student_case(cls.case, cls.other_student)
        cls.dossier_url = reverse("dossier:dossier", args=[cls.case.pk])
        cls.submit_url = reverse("dossier:submit_student_case", args=[cls.case.pk])

    def complete_data(self):
        return {
            "text": "Ingevuld", "number": "0", "date": "2026-10-15",
            "datetime": "2026-10-15T10:30", "choice": "Nee",
            "matrix": {"0_0": "0", "0_1": "", "1_0": "", "1_1": ""},
            "observations": [{"timestamp": "2026-10-15T10:30", "value": "Rustig", "note": "Controle"}],
        }

    def form_data(self, **changes):
        payload = {f"field_{key}": value for key, value in self.complete_data().items() if key not in {"matrix", "observations"}}
        payload.update({f"field_matrix_{key}": value for key, value in self.complete_data()["matrix"].items()})
        payload.update({"module": self.response.pk, "action": "save"})
        payload.update(changes)
        return payload

    def target(self, role):
        self.client.force_login(self.teacher if role == "teacher" else self.student)
        if role == "teacher":
            return reverse("dossier:teacher_module", args=[self.case.pk, self.module.pk]), self.module, "base_data"
        return self.dossier_url, self.response, "data"

    def save_response(self, data):
        self.response.data = data
        self.response.save()

    def test_incomplete_drafts_can_be_saved_by_student_and_teacher(self):
        for role in ("student", "teacher"):
            with self.subTest(role=role):
                url, record, attribute = self.target(role)
                result = self.client.post(url, {"module": self.response.pk, "field_text": "Alvast bewaard", "action": "save"})
                self.assertEqual(result.status_code, 302)
                record.refresh_from_db()
                self.assertEqual(getattr(record, attribute)["text"], "Alvast bewaard")
                self.assertFalse(getattr(record, attribute).get("observations"))

    def test_each_required_snapshot_field_blocks_final_submission(self):
        self.client.force_login(self.student)
        for key in self.complete_data():
            with self.subTest(key=key):
                data = self.complete_data()
                del data[key]
                self.save_response(data)
                result = self.client.post(self.submit_url, {f"field_{key}": "unsaved request value"}, follow=True)
                self.student_case.refresh_from_db()
                self.assertEqual(self.student_case.status, StudentCase.Status.ACTIVE)
                self.assertIsNone(self.student_case.submitted_at)
                self.assertContains(result, f"Veld {key}")
                self.assertTrue(next(field for field in result.context["fields"] if field["key"] == key)["errors"])
        self.assertFalse(AuditEvent.objects.filter(action="student_case.submitted").exists())

    def test_final_submission_checks_every_module(self):
        self.save_response(self.complete_data())
        second = self.student_case.module_responses.create(
            title="Tweede module", schema=[{"key": "extra", "type": "short_text", "label": "Extra", "required": True}],
        )
        self.client.force_login(self.student)
        result = self.client.post(self.submit_url)
        self.assertRedirects(result, f"{self.dossier_url}?module={second.pk}&validate=1")
        self.student_case.refresh_from_db()
        self.assertEqual(self.student_case.status, StudentCase.Status.ACTIVE)

    def test_invalid_saved_values_block_final_submission(self):
        self.client.force_login(self.student)
        invalid = {
            "number": "NaN", "date": "2026-02-30", "datetime": "geen tijdstip",
            "choice": "Niet toegestaan", "matrix": {"0_0": 5},
            "observations": [{"timestamp": "ongeldig", "value": "Waarde"}],
        }
        for key, value in invalid.items():
            with self.subTest(key=key):
                data = self.complete_data()
                data[key] = value
                self.save_response(data)
                self.assertEqual(self.client.post(self.submit_url).status_code, 302)
                self.student_case.refresh_from_db()
                self.assertEqual(self.student_case.status, StudentCase.Status.ACTIVE)
                self.assertIsNone(self.student_case.submitted_at)

    def test_matrix_whitespace_and_unknown_cells_do_not_satisfy_required(self):
        data = self.complete_data()
        data["matrix"] = {"0_0": "  ", "unknown": "Geen echte cel"}
        self.save_response(data)
        self.client.force_login(self.student)
        result = self.client.post(self.submit_url, follow=True)
        self.assertContains(result, "Vul minstens één cel in.")
        self.student_case.refresh_from_db()
        self.assertEqual(self.student_case.status, StudentCase.Status.ACTIVE)

    def test_complete_snapshot_submits_despite_new_source_requirements(self):
        self.save_response(self.complete_data())
        ModuleField.objects.create(module=self.module, key="later", label="Later toegevoegd", field_type="short_text", required=True)
        self.client.force_login(self.student)
        self.assertRedirects(self.client.post(self.submit_url), reverse("dossier:case_detail", args=[self.case.pk]))
        self.student_case.refresh_from_db()
        self.assertEqual(self.student_case.status, StudentCase.Status.SUBMITTED)
        self.assertIsNotNone(self.student_case.submitted_at)
        self.assertEqual(AuditEvent.objects.filter(action="student_case.submitted").count(), 1)

    def test_snapshot_requirement_survives_source_becoming_optional(self):
        self.module.fields.update(required=False)
        self.client.force_login(self.student)
        self.client.post(self.submit_url)
        self.student_case.refresh_from_db()
        self.assertEqual(self.student_case.status, StudentCase.Status.ACTIVE)

    def test_complete_modules_do_not_bypass_assignment_submission(self):
        self.save_response(self.complete_data())
        self.submission.status = AssignmentSubmission.Status.RESUBMIT
        self.submission.save()
        self.client.force_login(self.student)
        result = self.client.post(self.submit_url, follow=True)
        self.assertContains(result, "Dien eerst alle opdrachten in.")
        self.student_case.refresh_from_db()
        self.assertEqual(self.student_case.status, StudentCase.Status.ACTIVE)

    def test_validation_errors_preserve_all_form_values_without_saving(self):
        raw_text = '  Tekst <script>alert("test")</script>  '
        for role in ("student", "teacher"):
            with self.subTest(role=role):
                url, record, attribute = self.target(role)
                original = deepcopy(getattr(record, attribute))
                payload = self.form_data(
                    field_text=raw_text, field_number="geen getal", field_date="geen datum",
                    field_datetime="geen tijd", field_choice="Eigen keuze", field_matrix_1_1="  Matrixtekst  ",
                    observation_timestamp_observations="fout tijdstip", observation_value_observations="Nieuwe observatie",
                    observation_note_observations="Onbewaarde toelichting",
                )
                result = self.client.post(url, payload)
                self.assertEqual(result.status_code, 200)
                fields = {field["key"]: field for field in result.context["fields"]}
                self.assertEqual(fields["text"]["value"], raw_text)
                self.assertEqual(fields["number"]["value"], "geen getal")
                self.assertEqual(fields["matrix"]["value"]["1_1"], "  Matrixtekst  ")
                self.assertContains(result, 'type="text" value="geen getal"')
                self.assertContains(result, 'value="Eigen keuze" selected')
                self.assertContains(result, 'value="Onbewaarde toelichting"')
                self.assertContains(result, str(escape(raw_text)))
                self.assertNotContains(result, '<script>alert("test")</script>')
                record.refresh_from_db()
                self.assertEqual(getattr(record, attribute), original)

    def test_both_save_buttons_store_other_edits_and_pending_observations(self):
        for role in ("student", "teacher"):
            for action in ("save", "add_observation:observations"):
                with self.subTest(role=role, action=action):
                    url, record, attribute = self.target(role)
                    setattr(record, attribute, {})
                    record.save()
                    result = self.client.post(url, self.form_data(
                        action=action, field_text="Ook bewaren", observation_timestamp_observations="2026-10-15T12:00",
                        observation_value_observations="Observatie", observation_note_observations="Toelichting",
                    ))
                    self.assertEqual(result.status_code, 302)
                    record.refresh_from_db()
                    stored = getattr(record, attribute)
                    self.assertEqual(stored["text"], "Ook bewaren")
                    self.assertEqual(stored["matrix"]["0_0"], "0")
                    self.assertEqual(stored["observations"], [{"timestamp": "2026-10-15T12:00", "value": "Observatie", "note": "Toelichting"}])

    def test_pending_observation_is_only_appended_after_other_errors_are_corrected(self):
        for role in ("student", "teacher"):
            with self.subTest(role=role):
                url, record, attribute = self.target(role)
                payload = self.form_data(
                    action="add_observation:observations", field_number="fout",
                    observation_timestamp_observations="2026-10-15T12:00", observation_value_observations="Nieuwe meting",
                )
                result = self.client.post(url, payload)
                self.assertEqual(result.status_code, 200)
                self.assertContains(result, 'value="Nieuwe meting"')
                record.refresh_from_db()
                self.assertFalse(getattr(record, attribute).get("observations"))
                payload["field_number"] = "12"
                self.assertEqual(self.client.post(url, payload).status_code, 302)
                record.refresh_from_db()
                self.assertEqual(len(getattr(record, attribute)["observations"]), 1)

    def test_invalid_observation_prevents_partial_save(self):
        for role in ("student", "teacher"):
            with self.subTest(role=role):
                url, record, attribute = self.target(role)
                result = self.client.post(url, self.form_data(
                    action="add_observation:observations", field_text="Onbewaard",
                    observation_timestamp_observations="ongeldig", observation_value_observations="Wel ingevuld",
                ))
                self.assertEqual(result.status_code, 200)
                self.assertContains(result, 'value="Onbewaard"')
                self.assertContains(result, 'value="ongeldig"')
                record.refresh_from_db()
                self.assertEqual(getattr(record, attribute), {})

    def test_multiple_pending_observations_save_together(self):
        self.response.schema.append({"key": "second", "type": "observation", "label": "Tweede observatie"})
        self.response.save()
        self.client.force_login(self.student)
        result = self.client.post(self.dossier_url, self.form_data(
            action="add_observation:observations", observation_timestamp_observations="2026-10-15T12:00",
            observation_value_observations="Eerste", observation_timestamp_second="2026-10-15T12:30",
            observation_value_second="Tweede",
        ))
        self.assertEqual(result.status_code, 302)
        self.response.refresh_from_db()
        self.assertEqual(self.response.data["observations"][0]["value"], "Eerste")
        self.assertEqual(self.response.data["second"][0]["value"], "Tweede")

    def test_locked_student_dossier_rejects_both_save_buttons(self):
        self.client.force_login(self.student)
        for status in (StudentCase.Status.SUBMITTED, StudentCase.Status.REVIEWED):
            self.student_case.status = status
            self.student_case.save()
            for action in ("save", "add_observation:observations"):
                with self.subTest(status=status, action=action):
                    self.client.post(self.dossier_url, self.form_data(
                        action=action, observation_timestamp_observations="2026-10-15T12:00",
                        observation_value_observations="Geblokkeerd",
                    ))
                    self.response.refresh_from_db()
                    self.assertEqual(self.response.data, {})
                    self.assertEqual(self.client.post(self.submit_url).status_code, 403)

    def test_foreign_or_missing_module_never_changes_first_response(self):
        self.client.force_login(self.student)
        for identifier in (self.other_case.module_responses.get().pk, "invalid", ""):
            with self.subTest(identifier=identifier):
                result = self.client.post(self.dossier_url, self.form_data(module=identifier))
                self.assertEqual(result.status_code, 404)
                self.response.refresh_from_db()
                self.assertEqual(self.response.data, {})

    def test_unknown_observation_cannot_mutate_data(self):
        for role in ("student", "teacher"):
            with self.subTest(role=role):
                url, record, attribute = self.target(role)
                self.assertEqual(self.client.post(url, self.form_data(action="add_observation:unknown")).status_code, 403)
                record.refresh_from_db()
                self.assertEqual(getattr(record, attribute), {})

    def test_revoked_access_and_teacher_ownership_still_apply(self):
        self.group.members.remove(self.student)
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(self.dossier_url, self.form_data()).status_code, 403)
        self.assertEqual(self.client.post(self.submit_url).status_code, 403)
        other_teacher = get_user_model().objects.create_user("other-workflow-teacher")
        other_teacher.epd_profile.role = Profile.Role.TEACHER
        other_teacher.epd_profile.save()
        self.client.force_login(other_teacher)
        self.assertEqual(self.client.post(reverse("dossier:teacher_module", args=[self.case.pk, self.module.pk]), self.form_data()).status_code, 404)
        self.assertEqual(self.client.post(self.submit_url).status_code, 403)

    def test_saving_teacher_base_data_does_not_change_started_student_work(self):
        url, _, _ = self.target("teacher")
        self.client.post(url, self.form_data(field_text="Nieuwe voorinvulling"))
        self.response.refresh_from_db()
        self.assertEqual(self.response.data, {})
