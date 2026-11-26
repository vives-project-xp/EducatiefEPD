import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from dossier.models import (
    Case,
    CaseFunctionSnapshot,
    AuditEvent,
    Education,
    FunctionDefinition,
    LibraryTemplate,
    LibraryTemplateFunction,
    ManagedForm,
    ManagedQuestion,
    ModuleResponse,
    Patient,
    Profile,
    TeachingGroup,
)
from dossier.services import copy_template_to_case, start_student_case


@override_settings(SECURE_SSL_REDIRECT=False)
class LibraryFunctionSyncTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.education = Education.objects.get(slug="vroedkunde")
        self.teacher = user_model.objects.create_user("library-teacher", password="testpass")
        self.teacher.epd_profile.role = Profile.Role.TEACHER
        self.teacher.epd_profile.education = self.education
        self.teacher.epd_profile.save()
        self.student = user_model.objects.create_user("library-student", password="testpass")
        self.student.epd_profile.education = self.education
        self.student.epd_profile.save()

        group = TeachingGroup.objects.create(
            name="Library test group", education=self.education, teacher=self.teacher
        )
        group.members.add(self.student)
        patient = Patient.objects.create(
            name="Test, Tessa", reference="LIBRARY-TEST", created_by=self.teacher
        )
        self.case = Case.objects.create(
            title="Library sync test",
            patient=patient,
            education=self.education,
            course="Vroedkunde",
            status=Case.Status.PUBLISHED,
            created_by=self.teacher,
        )
        self.case.allowed_groups.add(group)
        self.template = LibraryTemplate.objects.create(
            title="Onderdeel met functies",
            category=LibraryTemplate.Category.MODULE,
            education=self.education,
            created_by=self.teacher,
        )
        self.original_function, self.original_form, self.original_question = (
            self.create_function("Bestaande functie", "Bestaande vraag")
        )
        self.unrelated_function, self.unrelated_form, self.unrelated_question = (
            self.create_function("Ongewijzigde functie", "Ongewijzigde vraag")
        )
        self.module = copy_template_to_case(self.template, self.case)
        self.original_snapshot = CaseFunctionSnapshot.objects.get(
            module=self.module, source_function_id=self.original_function.id
        )
        self.unrelated_snapshot = CaseFunctionSnapshot.objects.get(
            module=self.module, source_function_id=self.unrelated_function.id
        )
        self.student_case, _ = start_student_case(self.case, self.student)
        self.response = self.student_case.module_responses.get(module=self.module)

    def create_function(self, title, question_text):
        function = FunctionDefinition.objects.create(
            title=title, kind=FunctionDefinition.Kind.FORM
        )
        form = ManagedForm.objects.create(function=function, title=title)
        question = ManagedQuestion.objects.create(
            form=form,
            field_type=ManagedQuestion.FieldType.TEXT,
            question=question_text,
        )
        LibraryTemplateFunction.objects.create(
            template=self.template,
            function=function,
            position=self.template.function_links.count(),
        )
        return function, form, question

    def add_library_function(self, title, question_text):
        function = FunctionDefinition.objects.create(
            title=title, kind=FunctionDefinition.Kind.FORM
        )
        form = ManagedForm.objects.create(function=function, title=title)
        question = ManagedQuestion.objects.create(
            form=form,
            field_type=ManagedQuestion.FieldType.TEXT,
            question=question_text,
        )
        response = self.client.post(
            reverse("dossier:library_detail", args=[self.template.id]),
            {"action": "add_function", "function_ids": [str(function.id)]},
        )
        self.assertEqual(response.status_code, 302)
        return function, form, question

    def test_accepting_addition_updates_case_and_student_epd(self):
        self.client.force_login(self.teacher)
        existing_key = (
            f"{self.original_snapshot.id}_{self.original_form.id}_{self.original_question.id}"
        )
        self.module.base_data = {"_functions": {existing_key: "Docentstandaard"}}
        self.module.save(update_fields=["base_data"])
        self.response.data = {"_functions": {existing_key: "Docentstandaard"}}
        self.response.source_data = {"_functions": {existing_key: "Docentstandaard"}}
        self.response.save(update_fields=["data", "source_data"])
        added_function, added_form, added_question = self.add_library_function(
            "Nieuwe functie", "Nieuwe vraag"
        )
        prompt = self.client.get(reverse("dossier:teacher_case", args=[self.case.id]))
        self.assertContains(prompt, "Functie(s) toegevoegd")
        self.assertContains(prompt, "Nieuwe functie")

        accepted = self.client.post(
            reverse(
                "dossier:teacher_published_module_resolve",
                args=[self.case.id, self.module.id],
            ),
            {"action": "sync_students"},
        )
        self.assertEqual(accepted.status_code, 302)
        self.module.refresh_from_db()
        self.template.refresh_from_db()
        self.assertEqual(self.module.source_template_version, self.template.version)
        original_after = CaseFunctionSnapshot.objects.get(pk=self.original_snapshot.pk)
        self.assertTrue(original_after.active)
        self.assertEqual(original_after.definition, self.original_snapshot.definition)

        added_snapshot = CaseFunctionSnapshot.objects.get(
            module=self.module, source_function_id=added_function.id, active=True
        )
        self.assertEqual(added_snapshot.definition["forms"][0]["questions"][0]["question"], "Nieuwe vraag")
        added_key = f"{added_snapshot.id}_{added_form.id}_{added_question.id}"
        self.assertEqual(
            self.module.base_data["_functions"][existing_key], "Docentstandaard"
        )
        self.assertNotIn(added_key, self.module.base_data["_functions"])
        self.assertEqual(
            self.response.data["_functions"][existing_key], "Docentstandaard"
        )
        self.assertNotIn(added_key, self.response.data["_functions"])

        self.client.force_login(self.teacher)
        teacher_page = self.client.get(
            reverse("dossier:teacher_module", args=[self.case.id, self.module.id]),
            {"function": added_snapshot.id},
        )
        self.assertContains(teacher_page, "Nieuwe vraag")

        self.client.force_login(self.student)
        student_page = self.client.get(
            reverse("dossier:dossier", args=[self.case.id]),
            {"module": self.response.id, "function": added_snapshot.id},
        )
        self.assertContains(student_page, "Nieuwe vraag")
        answer_key = f"{added_snapshot.id}_{added_form.id}_{added_question.id}"
        self.assertContains(
            student_page,
            f'name="function_{answer_key}" rows="5" class="js-tinymce" ></textarea>',
        )
        self.assertNotContains(student_page, "Bestaand antwoord")

        self.client.force_login(self.teacher)
        prompt_after = self.client.get(reverse("dossier:teacher_case", args=[self.case.id]))
        self.assertNotContains(prompt_after, "Bibliotheek gewijzigd")

    def test_accepting_removal_hides_function_but_preserves_student_answers(self):
        removed_key = (
            f"{self.original_snapshot.id}_{self.original_form.id}_{self.original_question.id}"
        )
        unrelated_key = (
            f"{self.unrelated_snapshot.id}_{self.unrelated_form.id}_{self.unrelated_question.id}"
        )
        self.response.data = {
            "_functions": {
                removed_key: "Bestaand antwoord",
                unrelated_key: "Ongewijzigd antwoord",
            }
        }
        self.response.save(update_fields=["data"])
        original_definition = self.original_snapshot.definition
        unrelated_definition = self.unrelated_snapshot.definition
        self.client.force_login(self.teacher)

        deleted = self.client.post(
            reverse("dossier:function_action", args=[self.original_function.id]),
            data=json.dumps({"action": "delete"}),
            content_type="application/json",
        )
        self.assertEqual(deleted.status_code, 200)
        prompt = self.client.get(reverse("dossier:teacher_case", args=[self.case.id]))
        self.assertContains(prompt, "Functie(s) verwijderd")
        self.assertContains(prompt, "Bestaande functie")

        accepted = self.client.post(
            reverse(
                "dossier:teacher_published_module_resolve",
                args=[self.case.id, self.module.id],
            ),
            {"action": "sync_students"},
        )
        self.assertEqual(accepted.status_code, 302)
        removed_snapshot = CaseFunctionSnapshot.objects.get(pk=self.original_snapshot.pk)
        unrelated_snapshot = CaseFunctionSnapshot.objects.get(pk=self.unrelated_snapshot.pk)
        self.assertFalse(removed_snapshot.active)
        self.assertEqual(removed_snapshot.definition, original_definition)
        self.assertTrue(unrelated_snapshot.active)
        self.assertEqual(unrelated_snapshot.definition, unrelated_definition)

        self.response.refresh_from_db()
        self.assertEqual(self.response.data["_functions"][removed_key], "Bestaand antwoord")
        self.assertEqual(self.response.data["_functions"][unrelated_key], "Ongewijzigd antwoord")
        self.assertTrue(ModuleResponse.objects.filter(pk=self.response.pk).exists())
        self.module.refresh_from_db()
        self.template.refresh_from_db()
        self.assertEqual(self.module.source_template_version, self.template.version)

        self.client.force_login(self.student)
        student_page = self.client.get(
            reverse("dossier:dossier", args=[self.case.id]),
            {"module": self.response.id},
        )
        self.assertNotContains(student_page, "Bestaande functie")
        self.assertNotContains(student_page, "Bestaande vraag")
        self.assertContains(student_page, "Ongewijzigde functie")
        self.assertContains(student_page, "Ongewijzigde vraag")

        self.client.force_login(self.teacher)
        restored = self.client.post(
            reverse("dossier:function_trash_action"),
            data=json.dumps({
                "action": "restore",
                "functionId": self.original_function.id,
            }),
            content_type="application/json",
        )
        self.assertEqual(restored.status_code, 200)
        reattached = self.client.post(
            reverse("dossier:library_detail", args=[self.template.id]),
            {
                "action": "add_function",
                "function_ids": [str(self.original_function.id)],
            },
        )
        self.assertEqual(reattached.status_code, 302)
        reapplied = self.client.post(
            reverse(
                "dossier:teacher_published_module_resolve",
                args=[self.case.id, self.module.id],
            ),
            {"action": "sync_students"},
        )
        self.assertEqual(reapplied.status_code, 302)
        removed_snapshot.refresh_from_db()
        self.assertTrue(removed_snapshot.active)
        self.response.refresh_from_db()
        self.assertEqual(self.response.data["_functions"][removed_key], "Bestaand antwoord")

    def test_deny_is_persisted_for_one_version_and_prompts_again_after_change(self):
        self.case.status = Case.Status.DRAFT
        self.case.save(update_fields=["status"])
        self.module.base_data = {"existing": "unchanged"}
        self.module.save(update_fields=["base_data"])
        self.response.data = {"existing": "student answer"}
        self.response.save(update_fields=["data"])
        self.client.force_login(self.teacher)
        self.add_library_function("Afgewezen functie", "Afgewezen vraag")
        copy_template_to_case(self.template, self.case)
        self.module.refresh_from_db()
        self.assertEqual(self.module.source_template_version, 1)
        prompt = self.client.get(reverse("dossier:teacher_case", args=[self.case.id]))
        self.assertContains(prompt, "Afgewezen functie")

        denied = self.client.post(
            reverse(
                "dossier:teacher_removed_module_resolve",
                args=[self.case.id, self.module.id],
            ),
            {"action": "keep"},
        )
        self.assertEqual(denied.status_code, 302)
        self.module.refresh_from_db()
        self.template.refresh_from_db()
        self.assertEqual(self.module.source_template_version, 1)
        self.assertEqual(
            self.module.configuration["library_change_handled_version"],
            self.template.version,
        )
        self.assertEqual(self.module.base_data, {"existing": "unchanged"})
        self.response.refresh_from_db()
        self.assertEqual(self.response.data, {"existing": "student answer"})
        denial = AuditEvent.objects.get(
            action="library.change_denied",
            target_type="Module",
            target_id=str(self.module.id),
        )
        self.assertEqual(denial.actor, self.teacher)
        self.assertEqual(denial.details["version"], self.template.version)
        self.assertEqual(
            list(self.module.function_snapshots.values_list("id", "active", "definition")),
            [
                (self.original_snapshot.id, True, self.original_snapshot.definition),
                (self.unrelated_snapshot.id, True, self.unrelated_snapshot.definition),
            ],
        )
        dismissed = self.client.get(reverse("dossier:teacher_case", args=[self.case.id]))
        self.assertNotContains(dismissed, "Bibliotheek gewijzigd")

        self.add_library_function("Nieuwe wijziging", "Nieuwe vraag")
        prompted_again = self.client.get(reverse("dossier:teacher_case", args=[self.case.id]))
        self.assertContains(prompted_again, "Bibliotheek gewijzigd")
        self.assertContains(prompted_again, "Nieuwe wijziging")
        self.assertContains(prompted_again, "Afgewezen functie")
