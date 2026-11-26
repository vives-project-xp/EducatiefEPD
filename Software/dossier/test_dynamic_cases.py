from copy import deepcopy
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    Assignment, Case, Education, LibraryDossier, LibraryDossierModule,
    LibraryField, LibraryTemplate, Module, ModuleField, Patient, Profile,
    StudentCase, TeachingGroup,
)
from .services import (
    copy_library_dossier_to_case,
    start_student_case,
    synchronize_dossier_additions_to_cases,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class DynamicCaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.education = Education.objects.get(slug="vroedkunde")
        cls.teacher = get_user_model().objects.create_user("dynamic-teacher")
        cls.teacher.epd_profile.role = Profile.Role.TEACHER
        cls.teacher.epd_profile.education = cls.education
        cls.teacher.epd_profile.save()
        cls.group = TeachingGroup.objects.create(
            name="Dynamische lesgroep", education=cls.education, teacher=cls.teacher
        )

    def setUp(self):
        self.client.force_login(self.teacher)

    def new_case(self, reference="DYNAMIC"):
        return Case.objects.create(
            title="Dynamische casus", education=self.education, course="Zorg",
            patient=Patient.objects.create(name="Fictief", reference=reference),
            created_by=self.teacher,
        )

    def new_bundle(self):
        dossier = LibraryDossier.objects.create(title="Gekozen dossier", education=self.education)
        templates = []
        for position, title in enumerate(("Intake", "Evaluatie")):
            template = LibraryTemplate.objects.create(
                title=title, education=self.education, category="questionnaire"
            )
            LibraryField.objects.create(template=template, key="notitie", label="Notitie", field_type="long_text")
            LibraryDossierModule.objects.create(dossier=dossier, template=template, position=position)
            templates.append(template)
        return dossier, templates

    def test_new_patient_and_case_start_without_modules_despite_existing_library(self):
        LibraryTemplate.objects.create(
            title="Oud standaardonderdeel", category="module", education=self.education,
            seed_key="vroedkunde-anamnese",
        )
        response = self.client.post(reverse("dossier:teacher_case_create"), {
            "patient-name": "Fictieve patiënt", "patient-reference": "DYNAMIC-POST",
            "patient-gender": "unknown", "case-title": "Nieuwe casus",
            "case-education": self.education.pk, "case-course": "Zorg",
        })
        case = Case.objects.get(patient__reference="DYNAMIC-POST")
        self.assertRedirects(response, reverse("dossier:teacher_case", args=[case.pk]))
        self.assertFalse(case.modules.exists())
        self.assertEqual(LibraryTemplate.objects.count(), 1)
        page = self.client.get(reverse("dossier:teacher_case", args=[case.pk]))
        self.assertContains(page, "Nog geen dossiermodules")
        self.assertNotContains(page, "vaste dossierstructuur")

    def test_selected_bundle_copies_exactly_its_active_modules_in_order_once(self):
        dossier, templates = self.new_bundle()
        LibraryTemplate.objects.create(title="Niet gekozen", category="module", education=self.education)
        archived = LibraryTemplate.objects.create(title="Gearchiveerd", category="module", status="archived")
        LibraryDossierModule.objects.create(dossier=dossier, template=archived, position=2)
        case = self.new_case()
        url = reverse("dossier:teacher_case_add_dossier", args=[case.pk])
        for _ in range(2):
            self.assertRedirects(self.client.post(url, {"dossier_id": dossier.pk}),
                                 reverse("dossier:teacher_case", args=[case.pk]))
        self.assertEqual(list(case.modules.values_list("source_template_id", flat=True)),
                         [template.pk for template in templates])
        self.assertEqual(list(case.modules.values_list("position", flat=True)), [0, 1])
        self.assertEqual([module.fields.count() for module in case.modules.all()], [1, 1])

    def test_student_snapshots_and_existing_cases_survive_source_changes(self):
        dossier, templates = self.new_bundle()
        existing = self.new_case("DYNAMIC-EXISTING")
        copied_modules = copy_library_dossier_to_case(dossier, existing)
        copied_modules[0].base_data = {"notitie": "Bestaande voorinvulling"}
        copied_modules[0].save(update_fields=["base_data"])
        student = get_user_model().objects.create_user("dynamic-student")
        first, _ = start_student_case(existing, student)
        response = first.module_responses.get(module=copied_modules[0])
        original_schema = deepcopy(response.schema)
        original_data = deepcopy(response.data)
        templates[0].fields.update(label="Nieuw bronlabel")
        templates[0].title = "Nieuwe brontitel"
        templates[0].save()
        new = self.new_case("DYNAMIC-NEW")
        copy_library_dossier_to_case(dossier, new)
        self.assertEqual(new.modules.first().title, "Nieuwe brontitel")
        response.refresh_from_db()
        self.assertEqual(response.schema, original_schema)
        self.assertEqual(response.data, original_data)
        self.assertEqual(existing.modules.first().title, "Intake")
        self.assertEqual(existing.modules.count(), 2)
        self.assertEqual(first.module_responses.count(), 2)
        again, created = start_student_case(existing, student)
        self.assertFalse(created)
        self.assertEqual(again.pk, first.pk)

    def test_multiple_library_changes_are_shown_in_one_popup(self):
        dossier, templates = self.new_bundle()
        case = self.new_case("DYNAMIC-CHANGES")
        copy_library_dossier_to_case(dossier, case)

        page = self.client.get(reverse("dossier:teacher_case", args=[case.pk]))

        self.assertEqual(len(page.context["module_changes"]), 2)
        self.assertEqual(page.content.count(b'role="dialog"'), 1)
        self.assertContains(page, "Vorige versie behouden", count=2)
        self.assertContains(page, "Nieuwe versie gebruiken", count=2)
        for template in templates:
            self.assertContains(page, template.title)

        case.status = Case.Status.PUBLISHED
        case.save(update_fields=["status"])
        published_page = self.client.get(reverse("dossier:teacher_case", args=[case.pk]))

        self.assertEqual(len(published_page.context["module_changes"]), 2)
        self.assertEqual(published_page.content.count(b'role="dialog"'), 1)
        self.assertContains(published_page, "Vorige versie behouden", count=2)
        self.assertContains(published_page, "Nieuwe versie gebruiken", count=2)

    def test_readded_dossier_module_can_be_removed_again_after_being_kept(self):
        dossier, templates = self.new_bundle()
        case = self.new_case("DYNAMIC-READD")
        module = copy_library_dossier_to_case(dossier, case)[0]
        module.source_template_version = templates[0].version
        module.save(update_fields=["source_template_version"])

        dossier.module_entries.filter(template=templates[0]).delete()
        synchronize_dossier_additions_to_cases(dossier, {templates[0].pk})
        resolve_url = reverse(
            "dossier:teacher_removed_module_resolve", args=[case.pk, module.pk]
        )
        self.client.post(resolve_url, {"action": "keep"})

        LibraryDossierModule.objects.create(
            dossier=dossier, template=templates[0], position=0
        )
        synchronize_dossier_additions_to_cases(dossier, set())
        module.refresh_from_db()
        self.assertNotIn("library_removal_handled", module.configuration)

        page = self.client.get(reverse("dossier:teacher_case", args=[case.pk]))
        self.assertContains(page, "Wijzigingen in dossieronderdelen")
        self.assertContains(page, templates[0].title)

        self.client.post(resolve_url, {"action": "remove"})
        module.refresh_from_db()
        self.assertEqual(module.source_template_version, templates[0].version)

        dossier.module_entries.filter(template=templates[0]).delete()
        synchronize_dossier_additions_to_cases(dossier, {templates[0].pk})
        page = self.client.get(reverse("dossier:teacher_case", args=[case.pk]))

        self.assertContains(page, "Wijzigingen in dossieronderdelen")
        self.assertContains(page, templates[0].title)

    def test_removed_dossier_modules_are_detected_for_string_source_ids(self):
        dossier, templates = self.new_bundle()
        case = self.new_case("DYNAMIC-STRING-SOURCE")
        modules = copy_library_dossier_to_case(dossier, case)
        for module, template in zip(modules, templates):
            configuration = dict(module.configuration)
            configuration["source_library_dossier_id"] = str(dossier.pk)
            configuration["library_change_handled_version"] = template.version
            module.configuration = configuration
            module.source_template_version = template.version - 1
            module.save(update_fields=["configuration", "source_template_version"])

        dossier.module_entries.filter(template=templates[0]).delete()
        synchronize_dossier_additions_to_cases(dossier, {template.pk for template in templates})
        page = self.client.get(reverse("dossier:teacher_case", args=[case.pk]))

        self.assertEqual(len(page.context["module_changes"]), 1)
        self.assertEqual(
            [change["module"].pk for change in page.context["module_changes"]],
            [modules[0].pk],
        )
        self.assertContains(page, templates[0].title)

    def test_new_dossier_revision_reopens_previously_kept_removals(self):
        dossier, templates = self.new_bundle()
        case = self.new_case("DYNAMIC-REVISION")
        modules = copy_library_dossier_to_case(dossier, case)
        for module, template in zip(modules, templates):
            configuration = dict(module.configuration)
            configuration["library_change_handled_version"] = template.version
            module.configuration = configuration
            module.save(update_fields=["configuration"])

        dossier.module_entries.filter(template=templates[0]).delete()
        synchronize_dossier_additions_to_cases(dossier, {template.pk for template in templates})
        module = modules[0]
        module.refresh_from_db()
        module.configuration["library_removal_handled"] = True
        module.save(update_fields=["configuration"])

        added_template = LibraryTemplate.objects.create(
            title="Nieuw dossieronderdeel",
            education=self.education,
            category=LibraryTemplate.Category.QUESTIONNAIRE,
        )
        LibraryDossierModule.objects.create(
            dossier=dossier, template=added_template, position=2
        )
        synchronize_dossier_additions_to_cases(dossier, {templates[1].pk})
        added_module = case.modules.get(source_template=added_template)

        page = self.client.get(reverse("dossier:teacher_case", args=[case.pk]))

        self.assertEqual(len(page.context["module_changes"]), 2)
        changed_module_ids = {
            change["module"].pk for change in page.context["module_changes"]
        }
        self.assertEqual(changed_module_ids, {modules[0].pk, added_module.pk})

    def test_removing_published_module_preserves_student_answers(self):
        dossier, _ = self.new_bundle()
        case = self.new_case("DYNAMIC-ANSWERS")
        module = copy_library_dossier_to_case(dossier, case)[0]
        case.status = Case.Status.PUBLISHED
        case.save(update_fields=["status"])
        student = get_user_model().objects.create_user("answer-preservation-student")
        student_case, _ = start_student_case(case, student)
        student_response = student_case.module_responses.get(module=module)
        student_response.data = {"notitie": "Bestaand antwoord"}
        student_response.save(update_fields=["data"])

        module.configuration["library_dossier_module_removed"] = True
        module.save(update_fields=["configuration"])
        response = self.client.post(
            reverse("dossier:teacher_published_module_resolve", args=[case.pk, module.pk]),
            {"action": "sync_students"},
        )

        self.assertEqual(response.status_code, 302)
        student_response.refresh_from_db()
        self.assertIsNone(student_response.module_id)
        self.assertEqual(student_response.data, {"notitie": "Bestaand antwoord"})

    def test_readded_module_reuses_student_answers_and_applies_latest_schema(self):
        dossier, templates = self.new_bundle()
        case = self.new_case("DYNAMIC-READD-ANSWERS")
        module = copy_library_dossier_to_case(dossier, case)[0]
        case.status = Case.Status.PUBLISHED
        case.save(update_fields=["status"])
        student = get_user_model().objects.create_user("readded-module-student")
        student_case, _ = start_student_case(case, student)
        student_response = student_case.module_responses.get(module=module)
        student_response.data = {"notitie": "Bestaand antwoord"}
        student_response.save(update_fields=["data"])

        dossier.module_entries.filter(template=templates[0]).delete()
        module.configuration["library_dossier_module_removed"] = True
        module.save(update_fields=["configuration"])
        self.client.post(
            reverse("dossier:teacher_published_module_resolve", args=[case.pk, module.pk]),
            {"action": "sync_students"},
        )
        student_response.refresh_from_db()
        self.assertIsNone(student_response.module_id)
        student_case.module_responses.create(
            title=module.title,
            schema=student_response.schema,
            data={"legacy_answer": "Ook behouden"},
        )

        templates[0].fields.filter(key="notitie").update(label="Gewijzigde notitie")
        LibraryField.objects.create(
            template=templates[0],
            key="nieuw",
            label="Nieuw veld",
            field_type="short_text",
        )
        templates[0].version += 1
        templates[0].save(update_fields=["version"])
        LibraryDossierModule.objects.create(
            dossier=dossier, template=templates[0], position=0
        )
        synchronize_dossier_additions_to_cases(dossier, {templates[1].pk})
        updated_module = case.modules.get(source_template=templates[0])

        reopened_case, created = start_student_case(case, student)
        self.assertFalse(created)
        self.assertEqual(reopened_case.module_responses.count(), 2)
        self.assertFalse(reopened_case.module_responses.filter(module__isnull=True).exists())
        updated_response = reopened_case.module_responses.get(module=updated_module)
        self.assertEqual(
            updated_response.data,
            {"notitie": "Bestaand antwoord", "legacy_answer": "Ook behouden"},
        )
        self.assertEqual(
            {field["key"] for field in updated_response.schema},
            {"notitie", "nieuw"},
        )
        self.assertEqual(
            next(field["label"] for field in updated_response.schema if field["key"] == "notitie"),
            "Gewijzigde notitie",
        )

    def test_module_reorder_updates_student_versions_on_republish(self):
        dossier, templates = self.new_bundle()
        case = self.new_case("DYNAMIC-REORDER")
        modules = copy_library_dossier_to_case(dossier, case)
        for module, template in zip(modules, templates):
            configuration = dict(module.configuration)
            configuration["library_change_handled_version"] = template.version
            module.configuration = configuration
            module.save(update_fields=["configuration"])
        Assignment.objects.create(case=case, title="Opdracht")
        case.status = Case.Status.PUBLISHED
        case.save(update_fields=["status"])
        student = get_user_model().objects.create_user("reorder-student")
        student_case, _ = start_student_case(case, student)
        response = student_case.module_responses.get(module=modules[0])
        response.data = {"notitie": "Antwoord behouden"}
        response.save(update_fields=["data"])

        draft_transition = self.client.post(
            reverse("dossier:teacher_case_transition", args=[case.pk]),
            {"action": "draft"},
        )
        self.assertEqual(draft_transition.status_code, 302)

        dossier.module_entries.all().delete()
        LibraryDossierModule.objects.create(
            dossier=dossier, template=templates[1], position=0
        )
        LibraryDossierModule.objects.create(
            dossier=dossier, template=templates[0], position=1
        )
        synchronize_dossier_additions_to_cases(dossier, {template.pk for template in templates})

        page = self.client.get(reverse("dossier:teacher_case", args=[case.pk]))
        self.assertEqual(len(page.context["module_changes"]), 2)
        self.client.post(
            reverse("dossier:teacher_removed_module_resolve", args=[case.pk, modules[1].pk]),
            {"action": "remove"},
        )
        self.assertEqual(
            list(case.modules.order_by("position").values_list("source_template_id", flat=True)),
            [templates[1].pk, templates[0].pk],
        )

        transition = self.client.post(
            reverse("dossier:teacher_case_transition", args=[case.pk]),
            {"action": "publish"},
        )

        self.assertEqual(transition.status_code, 302)
        student_case.refresh_from_db()
        response.refresh_from_db()
        self.assertEqual(response.data, {"notitie": "Antwoord behouden"})
        self.assertEqual(response.position, 1)
        self.assertEqual(
            student_case.module_responses.get(module=modules[1]).position,
            0,
        )

    def test_republish_updates_empty_student_values_without_overwriting_answers(self):
        dossier, _ = self.new_bundle()
        case = self.new_case("DYNAMIC-EMPTY-VALUES")
        module = copy_library_dossier_to_case(dossier, case)[0]
        module.base_data = {"notitie": "Oude standaardwaarde"}
        module.save(update_fields=["base_data"])
        Assignment.objects.create(case=case, title="Opdracht")
        case.status = Case.Status.PUBLISHED
        case.save(update_fields=["status"])

        students = [
            get_user_model().objects.create_user(username)
            for username in (
                "filled-default-student",
                "blank-default-student",
                "missing-default-student",
            )
        ]
        student_cases = [start_student_case(case, student)[0] for student in students]
        responses = [
            student_case.module_responses.get(module=module)
            for student_case in student_cases
        ]
        responses[0].data = {"notitie": "Studentantwoord"}
        responses[0].save(update_fields=["data"])
        responses[1].data = {"notitie": ""}
        responses[1].save(update_fields=["data"])
        responses[2].data = {}
        responses[2].save(update_fields=["data"])

        admin = get_user_model().objects.create_superuser(
            "base-data-draft-admin", password="test-only"
        )
        self.client.force_login(admin)
        self.client.post(
            reverse("dossier:teacher_case_transition", args=[case.pk]),
            {"action": "draft"},
        )
        edit_response = self.client.post(
            reverse("dossier:teacher_module", args=[case.pk, module.pk]),
            {"field_notitie": "Nieuwe standaardwaarde", "action": "save"},
        )
        self.assertRedirects(edit_response, reverse("dossier:teacher_case", args=[case.pk]))
        self.client.post(
            reverse("dossier:teacher_removed_module_resolve", args=[case.pk, module.pk]),
            {"action": "remove"},
        )
        self.client.post(
            reverse("dossier:teacher_case_transition", args=[case.pk]),
            {"action": "publish"},
        )

        for response in responses:
            response.refresh_from_db()
        self.assertEqual(responses[0].data, {"notitie": "Studentantwoord"})
        self.assertEqual(responses[1].data, {"notitie": "Nieuwe standaardwaarde"})
        self.assertEqual(responses[2].data, {"notitie": "Nieuwe standaardwaarde"})

    def test_published_base_data_change_prompts_and_syncs_empty_answers(self):
        dossier, _ = self.new_bundle()
        case = self.new_case("DYNAMIC-PUBLISHED-BASE-DATA")
        module = copy_library_dossier_to_case(dossier, case)[0]
        module.base_data = {"notitie": "Oude standaardwaarde"}
        module.save(update_fields=["base_data"])
        Assignment.objects.create(case=case, title="Opdracht")
        case.status = Case.Status.PUBLISHED
        case.save(update_fields=["status"])

        students = [
            get_user_model().objects.create_user(username)
            for username in ("base-answer-student", "base-empty-student")
        ]
        student_cases = [start_student_case(case, student)[0] for student in students]
        responses = [
            student_case.module_responses.get(module=module)
            for student_case in student_cases
        ]
        responses[0].data = {"notitie": "Studentantwoord"}
        responses[0].save(update_fields=["data"])
        responses[1].data = {"notitie": ""}
        responses[1].save(update_fields=["data"])

        admin = get_user_model().objects.create_superuser(
            "base-data-admin", password="test-only"
        )
        self.client.force_login(admin)
        edit_response = self.client.post(
            reverse("dossier:teacher_module", args=[case.pk, module.pk]),
            {"field_notitie": "Nieuwe standaardwaarde", "action": "save"},
        )
        self.assertRedirects(edit_response, reverse("dossier:teacher_case", args=[case.pk]))

        page = self.client.get(reverse("dossier:teacher_case", args=[case.pk]))
        self.assertContains(page, "Voorinvulling aangepast")
        self.assertEqual(len(page.context["module_changes"]), 1)
        responses[0].refresh_from_db()
        responses[1].refresh_from_db()
        self.assertEqual(responses[0].data, {"notitie": "Studentantwoord"})
        self.assertEqual(responses[1].data, {"notitie": ""})

        self.client.post(
            reverse("dossier:teacher_published_module_resolve", args=[case.pk, module.pk]),
            {"action": "sync_students"},
        )
        responses[0].refresh_from_db()
        responses[1].refresh_from_db()
        self.assertEqual(responses[0].data, {"notitie": "Studentantwoord"})
        self.assertEqual(responses[1].data, {"notitie": "Nieuwe standaardwaarde"})

    def test_returned_draft_can_resolve_removed_module_with_student_cases(self):
        dossier, _ = self.new_bundle()
        case = self.new_case("DYNAMIC-DRAFT-REMOVAL")
        module = copy_library_dossier_to_case(dossier, case)[0]
        case.status = Case.Status.PUBLISHED
        case.save(update_fields=["status"])
        student = get_user_model().objects.create_user("draft-removal-student")
        student_case, _ = start_student_case(case, student)
        student_response = student_case.module_responses.get(module=module)
        student_response.data = {"notitie": "Antwoord behouden"}
        student_response.save(update_fields=["data"])

        module.configuration["library_dossier_module_removed"] = True
        module.save(update_fields=["configuration"])
        transition = self.client.post(
            reverse("dossier:teacher_case_transition", args=[case.pk]),
            {"action": "draft"},
        )
        self.assertEqual(transition.status_code, 302)

        page = self.client.get(reverse("dossier:teacher_case", args=[case.pk]))
        self.assertContains(page, "Wijzigingen in dossieronderdelen")
        self.assertContains(page, "Vorige versie behouden")
        resolve = self.client.post(
            reverse("dossier:teacher_removed_module_resolve", args=[case.pk, module.pk]),
            {"action": "remove"},
        )

        self.assertEqual(resolve.status_code, 302)
        self.assertFalse(case.modules.filter(pk=module.pk).exists())
        student_response.refresh_from_db()
        self.assertIsNone(student_response.module_id)
        self.assertEqual(student_response.data, {"notitie": "Antwoord behouden"})

    def test_active_student_cases_receive_source_updates_without_losing_answers(self):
        case = self.new_case("DYNAMIC-SYNC")
        assignment = Assignment.objects.create(
            case=case, phase="Eerste", title="Eerste opdracht", content="Oude instructie"
        )
        module = Module.objects.create(
            case=case, title="Intake", instructions="Oude module-instructie"
        )
        ModuleField.objects.create(
            module=module, key="klachten", label="Klachten", field_type="long_text"
        )
        student = get_user_model().objects.create_user("sync-student")
        student_case, _ = start_student_case(case, student)
        response = student_case.module_responses.get(module=module)
        response.data = {"klachten": "Bestaand antwoord"}
        response.save(update_fields=["data"])
        submission = student_case.assignment_submissions.get(assignment=assignment)
        submission.answer = "Bestaand antwoord op opdracht"
        submission.save(update_fields=["answer"])

        assignment.title = "Nieuwe opdrachtnaam"
        assignment.content = "Nieuwe instructie"
        assignment.save()
        Assignment.objects.create(
            case=case, phase="Tweede", title="Nieuwe opdracht", content="Extra opdracht"
        )
        module.title = "Nieuwe mod bijnaam"
        module.instructions = "Nieuwe module-instructie"
        module.save(update_fields=["title", "instructions"])
        ModuleField.objects.create(
            module=module, key="allergieën", label="Allergieën", field_type="short_text"
        )

        start_student_case(case, student)

        response.refresh_from_db()
        submission.refresh_from_db()
        self.assertEqual(response.title, "Nieuwe mod bijnaam")
        self.assertEqual(response.instructions, "Nieuwe module-instructie")
        self.assertEqual(response.data, {"klachten": "Bestaand antwoord"})
        self.assertEqual({field["key"] for field in response.schema}, {"klachten", "allergieën"})
        self.assertEqual(submission.title, "Nieuwe opdrachtnaam")
        self.assertEqual(submission.content, "Nieuwe instructie")
        self.assertEqual(submission.answer, "Bestaand antwoord op opdracht")
        self.assertEqual(student_case.assignment_submissions.count(), 2)

    def test_submitted_student_cases_are_not_synchronized(self):
        case = self.new_case("DYNAMIC-LOCKED")
        Assignment.objects.create(case=case, title="Oude opdracht")
        module = Module.objects.create(case=case, title="Oude module")
        student = get_user_model().objects.create_user("locked-sync-student")
        student_case, _ = start_student_case(case, student)
        student_case.status = StudentCase.Status.SUBMITTED
        student_case.save(update_fields=["status"])
        Assignment.objects.create(case=case, title="Nieuwe opdracht")
        module.title = "Nieuwe module"
        module.save(update_fields=["title"])

        start_student_case(case, student)

        student_case.refresh_from_db()
        self.assertEqual(student_case.assignment_submissions.count(), 1)
        self.assertEqual(student_case.module_responses.get().title, "Oude module")

    def test_empty_case_cannot_be_published_before_choosing_modules(self):
        case = self.new_case()
        Assignment.objects.create(case=case, title="Opdracht", content="Test", phase="Eerste")
        url = reverse("dossier:teacher_case_transition", args=[case.pk])
        self.client.post(url, {"action": "publish"})
        case.refresh_from_db()
        self.assertEqual(case.status, Case.Status.DRAFT)
        dossier, _ = self.new_bundle()
        copy_library_dossier_to_case(dossier, case)
        self.client.post(url, {"action": "publish"})
        case.refresh_from_db()
        self.assertEqual(case.status, Case.Status.PUBLISHED)

    def test_auto_add_setting_is_absent_for_admin_and_teacher(self):
        admin = get_user_model().objects.create_superuser("dynamic-admin", password="test-only")
        for user in (self.teacher, admin):
            with self.subTest(role=user.username):
                self.client.force_login(user)
                page = self.client.get(reverse("dossier:library_create"))
                self.assertNotIn("is_fixed", page.context["form"].fields)
                self.assertNotContains(page, "Automatisch toevoegen")

    def test_demo_uses_its_own_selected_bundle_and_is_repeatable(self):
        for _ in range(2):
            call_command("seed_demo", stdout=StringIO())
        case = Case.objects.get(patient__reference="VRK-IC1-MIA")
        dossier = LibraryDossier.objects.get(title="Demo: opname")
        self.assertEqual(list(case.modules.values_list("source_template_id", flat=True)),
                         list(dossier.module_entries.values_list("template_id", flat=True)))
        self.assertEqual(case.modules.count(), 1)
        self.assertEqual(LibraryTemplate.objects.count(), 1)
