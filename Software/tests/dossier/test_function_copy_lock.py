import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from dossier.models import (
    Education,
    FunctionDefinition,
    LibraryTemplate,
    LibraryTemplateFunction,
    ManagedForm,
    ManagedQuestion,
    Profile,
)
from .fixtures import create_library_fixtures


@override_settings(SECURE_SSL_REDIRECT=False)
class FunctionCopyAndLockTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_library_fixtures()
        cls.education = Education.objects.get(slug="vroedkunde")
        user_model = get_user_model()
        cls.teacher_a = user_model.objects.create_user("lock-owner")
        cls.teacher_b = user_model.objects.create_user("other-teacher")
        cls.manager_a = user_model.objects.create_user("manager-a")
        cls.manager_b = user_model.objects.create_user("manager-b")
        for user, role in (
            (cls.teacher_a, Profile.Role.TEACHER),
            (cls.teacher_b, Profile.Role.TEACHER),
            (cls.manager_a, Profile.Role.ADMIN),
            (cls.manager_b, Profile.Role.ADMIN),
        ):
            user.epd_profile.role = role
            user.epd_profile.education = cls.education
            user.epd_profile.save()

    def setUp(self):
        self.function = FunctionDefinition.objects.create(
            title="Zorgfunctie", kind=FunctionDefinition.Kind.GROUP
        )
        self.forms = [
            ManagedForm.objects.create(
                function=self.function,
                title=f"Formulier {index}",
                position=index - 1,
            )
            for index in range(1, 4)
        ]
        for index, form in enumerate(self.forms, 1):
            ManagedQuestion.objects.create(
                form=form,
                position=0,
                field_type=ManagedQuestion.FieldType.TEXT,
                question=f"Vraag {index}",
                required=index == 1,
            )

    def action(self, user, payload, function=None):
        self.client.force_login(user)
        return self.client.post(
            reverse("dossier:function_action", args=[(function or self.function).pk]),
            json.dumps(payload),
            content_type="application/json",
        )

    def lock_as(self, user, function=None):
        response = self.action(user, {"action": "toggle_lock"}, function)
        self.assertEqual(response.status_code, 200, response.content)
        locked_function = function or self.function
        locked_function.refresh_from_db()
        self.assertTrue(locked_function.locked)
        self.assertEqual(locked_function.locked_by_id, user.pk)

    def test_function_duplicate_copies_every_form_and_deep_copies_settings(self):
        matrix_definition = {
            "version": 2,
            "rows": [{"id": "row-a", "label": "Rij A"}],
            "columns": [{"id": "column-a", "label": "Kolom A"}],
            "settings": {"nested": [{"label": "Oorspronkelijk"}]},
        }
        matrix = ManagedQuestion.objects.create(
            form=self.forms[0],
            position=1,
            field_type=ManagedQuestion.FieldType.MATRIX,
            question="Matrix",
            unit="cm",
            required=True,
            options=["optie"],
            rows=["Rij A"],
            columns=["Kolom A"],
            matrix_definition=matrix_definition,
        )
        observation = ManagedQuestion.objects.create(
            form=self.forms[1],
            position=1,
            field_type=ManagedQuestion.FieldType.OBSERVATION,
            question="Observatie",
            required=True,
            unit="bpm",
            explanation="Toelichting",
        )
        image = ManagedQuestion.objects.create(
            form=self.forms[2],
            position=1,
            field_type=ManagedQuestion.FieldType.IMAGE,
            question="Afbeelding",
            image="data:image/png;base64,AA==",
            caption="Bijschrift",
        )
        template = LibraryTemplate.objects.create(
            title="Onderdeel",
            category=LibraryTemplate.Category.MODULE,
            created_by=self.teacher_a,
        )
        LibraryTemplateFunction.objects.create(
            template=template, function=self.function, position=0
        )

        response = self.action(self.teacher_a, {"action": "duplicate"})

        self.assertEqual(response.status_code, 200, response.content)
        duplicate = FunctionDefinition.objects.get(
            title="Zorgfunctie (kopie)"
        )
        self.assertEqual(duplicate.kind, self.function.kind)
        self.assertFalse(duplicate.std)
        self.assertFalse(duplicate.locked)
        self.assertIsNone(duplicate.locked_by_id)
        self.assertFalse(duplicate.template_links.exists())
        duplicate_forms = list(duplicate.forms.order_by("position"))
        self.assertEqual([form.title for form in duplicate_forms], [
            "Formulier 1", "Formulier 2", "Formulier 3",
        ])
        copied_matrix = duplicate_forms[0].questions.get(question="Matrix")
        self.assertEqual(copied_matrix.matrix_definition, matrix_definition)
        self.assertEqual(copied_matrix.options, ["optie"])
        self.assertEqual(copied_matrix.rows, ["Rij A"])
        self.assertEqual(copied_matrix.columns, ["Kolom A"])
        copied_observation = duplicate_forms[1].questions.get(question="Observatie")
        self.assertEqual(copied_observation.field_type, ManagedQuestion.FieldType.OBSERVATION)
        self.assertEqual(copied_observation.unit, "bpm")
        copied_image = duplicate_forms[2].questions.get(question="Afbeelding")
        self.assertEqual(copied_image.image, image.image)
        self.assertEqual(copied_image.caption, "Bijschrift")

        copied_matrix.matrix_definition["settings"]["nested"][0]["label"] = "Kopie"
        copied_matrix.save(update_fields=["matrix_definition"])
        matrix.refresh_from_db()
        self.assertEqual(
            matrix.matrix_definition["settings"]["nested"][0]["label"],
            "Oorspronkelijk",
        )
        matrix.matrix_definition["settings"]["nested"][0]["label"] = "Origineel aangepast"
        matrix.save(update_fields=["matrix_definition"])
        copied_matrix.refresh_from_db()
        self.assertEqual(
            copied_matrix.matrix_definition["settings"]["nested"][0]["label"],
            "Kopie",
        )

        second_copy_response = self.action(self.teacher_a, {"action": "duplicate"})
        self.assertEqual(second_copy_response.status_code, 200)
        self.assertTrue(FunctionDefinition.objects.filter(
            title="Zorgfunctie (kopie 2)"
        ).exists())

    def test_standard_function_can_be_duplicated_without_copying_standard_lock(self):
        standard = FunctionDefinition.objects.create(
            title="Standaardfunctie",
            kind=FunctionDefinition.Kind.FORM,
            std=True,
            locked=True,
        )
        ManagedForm.objects.create(function=standard, title=standard.title)

        response = self.action(
            self.teacher_a, {"action": "duplicate"}, function=standard
        )

        self.assertEqual(response.status_code, 200, response.content)
        duplicate = FunctionDefinition.objects.get(title="Standaardfunctie (kopie)")
        self.assertFalse(duplicate.std)
        self.assertFalse(duplicate.locked)
        self.assertIsNone(duplicate.locked_by_id)
        standard.refresh_from_db()
        self.assertTrue(standard.std)
        self.assertTrue(standard.locked)

    def test_function_list_exposes_copy_for_standards_and_disables_locked_edits(self):
        standard = FunctionDefinition.objects.create(
            title="Standaard kopieerbaar",
            kind=FunctionDefinition.Kind.FORM,
            std=True,
            locked=True,
        )
        self.lock_as(self.teacher_a)
        self.client.force_login(self.teacher_b)

        response = self.client.get(reverse("dossier:function_management"))

        self.assertContains(response, f'data-duplicate-function data-url="/bibliotheek/functies-beheer/{standard.pk}/actie/"')
        self.assertContains(response, f'data-duplicate-function data-url="/bibliotheek/functies-beheer/{self.function.pk}/actie/" aria-label="Dupliceren: Zorgfunctie" disabled')
        self.assertContains(response, "Standaard kopieerbaar")

    def test_form_duplicate_inserts_after_source_with_independent_questions(self):
        source = self.forms[1]
        question = ManagedQuestion.objects.create(
            form=source,
            position=1,
            field_type=ManagedQuestion.FieldType.MATRIX,
            question="Matrixvraag",
            matrix_definition={"version": 2, "settings": {"labels": ["Bron"]}},
        )

        response = self.action(self.teacher_a, {
            "action": "duplicate_form",
            "formId": source.pk,
        })

        self.assertEqual(response.status_code, 200, response.content)
        duplicate_id = response.json()["formId"]
        forms = list(self.function.forms.order_by("position"))
        self.assertEqual([form.title for form in forms], [
            "Formulier 1", "Formulier 2", "Formulier 2 (kopie)", "Formulier 3",
        ])
        self.assertEqual([form.position for form in forms], [0, 1, 2, 3])
        duplicate = forms[2]
        self.assertEqual(duplicate.pk, duplicate_id)
        copied_question = duplicate.questions.get(question="Matrixvraag")
        self.assertEqual(copied_question.matrix_definition, question.matrix_definition)
        copied_question.matrix_definition["settings"]["labels"][0] = "Kopie"
        copied_question.save(update_fields=["matrix_definition"])
        question.refresh_from_db()
        self.assertEqual(question.matrix_definition["settings"]["labels"], ["Bron"])

    def test_duplicate_only_form_converts_form_to_group(self):
        single = FunctionDefinition.objects.create(
            title="Los formulier", kind=FunctionDefinition.Kind.FORM
        )
        form = ManagedForm.objects.create(function=single, title=single.title)
        ManagedQuestion.objects.create(
            form=form,
            field_type=ManagedQuestion.FieldType.OBSERVATION,
            question="Waarneming",
            required=True,
        )

        response = self.action(
            self.teacher_a,
            {"action": "duplicate_form", "formId": form.pk},
            function=single,
        )

        self.assertEqual(response.status_code, 200, response.content)
        single.refresh_from_db()
        forms = list(single.forms.order_by("position"))
        self.assertEqual(single.kind, FunctionDefinition.Kind.GROUP)
        self.assertEqual([item.title for item in forms], [
            "Los formulier", "Los formulier (kopie)",
        ])
        self.assertEqual(forms[1].questions.get().field_type, ManagedQuestion.FieldType.OBSERVATION)
        self.assertIn(f"?form={forms[1].pk}", response.json()["redirect"])

    def test_other_teacher_cannot_unlock_or_mutate_locked_function(self):
        self.lock_as(self.teacher_a)
        self.client.force_login(self.teacher_b)
        page = self.client.get(reverse(
            "dossier:function_detail", args=[self.function.pk]
        ))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Vergrendeld door lock-owner")
        self.assertContains(page, 'data-locked="true"')
        self.assertContains(page, 'data-lock aria-pressed="true" disabled')
        self.assertFalse(page.context["can_toggle_lock"])
        self.assertIn("lock-owner", page.context["function_data"]["lockedByName"])

        attempts = [
            {"action": "toggle_lock"},
            {"action": "rename", "title": "Niet toegestaan"},
            {"action": "delete"},
            {"action": "duplicate"},
            {"action": "create_form"},
            {"action": "reorder_forms", "formIds": [form.pk for form in self.forms]},
            {"action": "delete_form", "formId": self.forms[0].pk},
            {"action": "duplicate_form", "formId": self.forms[0].pk},
            {"action": "save_form", "formId": self.forms[0].pk, "title": "Formulier 1", "questions": []},
        ]
        for payload in attempts:
            with self.subTest(action=payload["action"]):
                response = self.action(self.teacher_b, payload)
                self.assertEqual(response.status_code, 403)
                self.assertIn("lock-owner", response.json()["message"])

        self.function.refresh_from_db()
        self.assertTrue(self.function.locked)
        self.assertEqual(self.function.locked_by_id, self.teacher_a.pk)
        self.assertEqual(self.function.forms.count(), 3)

    def test_lock_owner_can_unlock_and_then_edit(self):
        self.lock_as(self.teacher_a)

        unlock = self.action(self.teacher_a, {"action": "toggle_lock"})
        self.assertEqual(unlock.status_code, 200)
        self.function.refresh_from_db()
        self.assertFalse(self.function.locked)
        self.assertIsNone(self.function.locked_by_id)

        edit = self.action(self.teacher_a, {
            "action": "rename",
            "title": "Bijgewerkt",
        })
        self.assertEqual(edit.status_code, 200)
        self.function.refresh_from_db()
        self.assertEqual(self.function.title, "Bijgewerkt")

    def test_managers_can_edit_and_unlock_any_lock(self):
        self.lock_as(self.teacher_a)

        self.client.force_login(self.manager_a)
        response = self.client.get(reverse(
            "dossier:function_detail", args=[self.function.pk]
        ))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["function_data"]["isManager"])
        self.assertTrue(response.context["can_toggle_lock"])
        self.assertNotContains(response, 'data-lock aria-pressed="true" disabled')
        edit = self.action(self.manager_a, {
            "action": "rename",
            "title": "Beheerderswijziging",
        })
        self.assertEqual(edit.status_code, 200)
        save = self.action(self.manager_a, {
            "action": "save_form",
            "formId": self.forms[0].pk,
            "title": self.forms[0].title,
            "questions": [{
                "fieldType": ManagedQuestion.FieldType.TEXT,
                "question": "Manager bewerkte dit",
            }],
        })
        self.assertEqual(save.status_code, 200, save.content)
        self.assertTrue(self.forms[0].questions.filter(
            question="Manager bewerkte dit"
        ).exists())
        self.function.refresh_from_db()
        self.assertTrue(self.function.locked)
        self.assertEqual(self.function.locked_by_id, self.teacher_a.pk)

        unlock = self.action(self.manager_a, {"action": "toggle_lock"})
        self.assertEqual(unlock.status_code, 200)
        self.function.refresh_from_db()
        self.assertFalse(self.function.locked)
        self.assertIsNone(self.function.locked_by_id)

    def test_manager_lock_blocks_teachers_but_another_manager_can_unlock(self):
        self.lock_as(self.manager_a)
        denied = self.action(self.teacher_b, {"action": "toggle_lock"})
        self.assertEqual(denied.status_code, 403)
        self.assertIn("manager-a", denied.json()["message"])

        unlock = self.action(self.manager_b, {"action": "toggle_lock"})
        self.assertEqual(unlock.status_code, 200)
        self.function.refresh_from_db()
        self.assertFalse(self.function.locked)
        self.assertIsNone(self.function.locked_by_id)

    def test_legacy_lock_without_owner_is_manager_only(self):
        self.function.locked = True
        self.function.save(update_fields=["locked"])

        denied = self.action(self.teacher_b, {"action": "toggle_lock"})
        self.assertEqual(denied.status_code, 403)
        self.assertIn("onbekende gebruiker", denied.json()["message"])

        unlocked = self.action(self.manager_a, {"action": "toggle_lock"})
        self.assertEqual(unlocked.status_code, 200)
        self.function.refresh_from_db()
        self.assertFalse(self.function.locked)

    def test_locked_functions_cannot_be_attached_or_detached_by_teachers(self):
        self.lock_as(self.teacher_a)
        attached = LibraryTemplate.objects.create(
            title="Bestaand onderdeel",
            category=LibraryTemplate.Category.MODULE,
            created_by=self.teacher_a,
        )
        available = LibraryTemplate.objects.create(
            title="Ander onderdeel",
            category=LibraryTemplate.Category.MODULE,
            created_by=self.teacher_a,
        )
        link = LibraryTemplateFunction.objects.create(
            template=attached, function=self.function, position=0
        )
        self.client.force_login(self.teacher_b)

        page = self.client.get(reverse(
            "dossier:library_detail", args=[attached.pk]
        ))
        self.assertContains(page, "Vergrendeld door lock-owner")
        self.assertNotIn(
            self.function,
            list(page.context["available_functions"]),
        )
        remove = self.client.post(reverse(
            "dossier:library_detail", args=[attached.pk]
        ), {"action": "remove_function", "function_id": self.function.pk})
        self.assertEqual(remove.status_code, 403)
        self.assertTrue(LibraryTemplateFunction.objects.filter(pk=link.pk).exists())
        add = self.client.post(reverse(
            "dossier:library_detail", args=[available.pk]
        ), {"action": "add_function", "function_ids": [self.function.pk]})
        self.assertEqual(add.status_code, 403)
        self.assertFalse(available.function_links.exists())

    def test_locked_functions_cannot_be_permanently_deleted_from_trash_by_teachers(self):
        self.lock_as(self.teacher_a)
        self.function.deleted_at = timezone.now()
        self.function.save(update_fields=["deleted_at"])
        self.client.force_login(self.teacher_b)

        permanent_delete = self.client.post(
            reverse("dossier:function_trash_action"),
            json.dumps({"action": "permanent_delete", "functionId": self.function.pk}),
            content_type="application/json",
        )
        self.assertEqual(permanent_delete.status_code, 403)
        self.assertTrue(FunctionDefinition.objects.filter(pk=self.function.pk).exists())
        empty = self.client.post(
            reverse("dossier:function_trash_action"),
            json.dumps({"action": "empty"}),
            content_type="application/json",
        )
        self.assertEqual(empty.status_code, 403)
        self.assertTrue(FunctionDefinition.objects.filter(pk=self.function.pk).exists())
        self.function.deleted_at = timezone.now() - timedelta(days=31)
        self.function.save(update_fields=["deleted_at"])
        self.client.get(reverse("dossier:function_management"))
        self.assertTrue(FunctionDefinition.objects.filter(pk=self.function.pk).exists())

        self.client.force_login(self.manager_a)
        allowed = self.client.post(
            reverse("dossier:function_trash_action"),
            json.dumps({"action": "permanent_delete", "functionId": self.function.pk}),
            content_type="application/json",
        )
        self.assertEqual(allowed.status_code, 200, allowed.content)
        self.assertFalse(FunctionDefinition.objects.filter(pk=self.function.pk).exists())
