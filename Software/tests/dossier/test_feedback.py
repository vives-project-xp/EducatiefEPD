"""Docentfeedback: saneren, beoordelingsformulier, geschiedenis en modulefeedback."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from dossier.models import (
    Assignment,
    AssignmentReview,
    AssignmentSubmission,
    AuditEvent,
    Case,
    Education,
    LibraryField,
    LibraryTemplate,
    Patient,
    Profile,
    StudentCase,
    TeachingGroup,
)
from dossier.services import (
    clean_html,
    copy_template_to_case,
    render_rich_text,
    start_student_case,
)


class RichTextSanitizingTests(TestCase):
    def test_clean_html_keeps_editor_colours_and_strips_active_content(self):
        cleaned = clean_html(
            '<p><span style="color: #e03e2d; position: fixed">rood</span>'
            '<span style="background-color: #fbeeb8">geel</span></p>'
            '<script>alert(1)</script><img src="x" onerror="alert(1)">'
            '<a href="javascript:alert(1)">link</a>'
        )
        self.assertIn('style="color:#e03e2d"', cleaned)
        self.assertIn('style="background-color:#fbeeb8"', cleaned)
        self.assertNotIn("position", cleaned)
        self.assertNotIn("<script", cleaned)
        self.assertNotIn("onerror", cleaned)
        self.assertNotIn("javascript:", cleaned)

    def test_plain_text_keeps_line_breaks_and_is_escaped(self):
        self.assertEqual(str(render_rich_text("a < b\nc")), "<p>a &lt; b<br>c</p>")

    def test_editor_html_is_not_wrapped_again(self):
        self.assertEqual(str(render_rich_text("<p>Een</p>\n<p>Twee</p>")), "<p>Een</p>\n<p>Twee</p>")


@override_settings(SECURE_SSL_REDIRECT=False)
class TeacherFeedbackTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.education = Education.objects.get(slug="vroedkunde")
        cls.teacher = users.create_user("fb-teacher", password="testpass", first_name="Docent")
        cls.teacher.epd_profile.role = Profile.Role.TEACHER
        cls.teacher.epd_profile.education = cls.education
        cls.teacher.epd_profile.save()
        cls.student = users.create_user("fb-student", password="testpass")
        cls.student.epd_profile.education = cls.education
        cls.student.epd_profile.save()
        patient = Patient.objects.create(name="Feedback, Fien", reference="FB-1", created_by=cls.teacher)
        cls.case = Case.objects.create(
            title="Feedbackcasus", patient=patient, education=cls.education,
            course="Vroedkunde", introduction="Inleiding", created_by=cls.teacher,
            status=Case.Status.PUBLISHED,
        )
        group = TeachingGroup.objects.create(name="FB-groep", education=cls.education, teacher=cls.teacher)
        group.members.add(cls.student)
        cls.case.allowed_groups.add(group)
        template = LibraryTemplate.objects.create(
            title="Anamnese", category="questionnaire", theme="Opname", education=cls.education,
        )
        LibraryField.objects.create(
            template=template, label="Reden van opname", key="reden", field_type="long_text", position=0,
        )
        copy_template_to_case(template, cls.case)
        Assignment.objects.create(
            case=cls.case, phase="Opdracht 1", title="Observeer",
            content="<p>Beschrijf <strong>de observatie</strong>.</p>", position=1,
        )

    def setUp(self):
        self.student_case, _ = start_student_case(self.case, self.student)
        self.submission = self.student_case.assignment_submissions.get()
        self.module = self.student_case.module_responses.get()

    # -- helpers ---------------------------------------------------------
    def submit_answer(self, answer):
        self.client.force_login(self.student)
        return self.client.post(
            reverse("dossier:case_detail", args=[self.case.id]),
            {"assignment": self.submission.id, "answer": answer, "action": "submit"},
        )

    def review(self, status, feedback=""):
        self.client.force_login(self.teacher)
        return self.client.post(
            reverse("dossier:teacher_review_assignment", args=[self.student_case.id, self.submission.id]),
            {"status": status, "feedback": feedback},
        )

    def teacher_page(self):
        self.client.force_login(self.teacher)
        return self.client.get(reverse("dossier:teacher_student_case", args=[self.student_case.id]))

    # -- 1. saneren --------------------------------------------------------
    def test_student_answer_is_sanitized_when_saved(self):
        self.submit_answer('<p>Antwoord</p><script>alert(1)</script><img src="x" onerror="alert(1)">')
        self.submission.refresh_from_db()
        self.assertIn("<p>Antwoord</p>", self.submission.answer)
        self.assertNotIn("<script", self.submission.answer)
        self.assertNotIn("onerror", self.submission.answer)

    def test_review_page_neutralises_unsafe_answer_already_in_database(self):
        AssignmentSubmission.objects.filter(pk=self.submission.pk).update(
            answer='<p>Oud</p><script>alert("xss")</script><img src="x" onerror="alert(1)">',
            status=AssignmentSubmission.Status.SUBMITTED,
        )
        response = self.teacher_page()
        self.assertContains(response, "<p>Oud</p>")
        self.assertNotContains(response, 'alert("xss")')
        self.assertNotContains(response, "onerror")

    def test_feedback_is_sanitized_and_keeps_colour_for_student(self):
        self.submit_answer("<p>Antwoord</p>")
        self.review(
            "resubmit",
            '<p><span style="color: #e03e2d;">Fout</span></p><script>alert(1)</script>',
        )
        self.submission.refresh_from_db()
        self.assertNotIn("<script", self.submission.feedback)
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("dossier:case_detail", args=[self.case.id]), {"assignment": self.submission.id}
        )
        self.assertContains(response, '<span style="color:#e03e2d">Fout</span>')
        self.assertNotContains(response, "<script>alert(1)")

    def test_unsafe_legacy_feedback_is_not_executed_for_student(self):
        AssignmentSubmission.objects.filter(pk=self.submission.pk).update(
            feedback='Goed<img src="x" onerror="alert(1)">', status=AssignmentSubmission.Status.APPROVED,
        )
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("dossier:case_detail", args=[self.case.id]), {"assignment": self.submission.id}
        )
        self.assertContains(response, "Goed")
        self.assertNotContains(response, "onerror")

    # -- 2. beoordelingsformulier -------------------------------------------
    def test_review_without_status_is_rejected_and_keeps_typed_feedback(self):
        self.submit_answer("<p>Antwoord</p>")
        response = self.review("", "Nog niet af, concepttekst")
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Kies een beoordeling.", status_code=400)
        self.assertContains(response, "Nog niet af, concepttekst", status_code=400)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, AssignmentSubmission.Status.SUBMITTED)
        self.assertEqual(self.submission.feedback, "")
        self.assertFalse(AssignmentReview.objects.exists())

    def test_first_review_has_no_default_status_and_rereview_preselects_current(self):
        self.submit_answer("<p>Antwoord</p>")
        form = self.teacher_page().context["student_case"].assignment_submissions.all()[0].review_form
        self.assertEqual(form.initial["status"], "")
        self.assertEqual(form.fields["status"].choices[0][0], "")
        self.review("approved", "Prima")
        form = self.teacher_page().context["student_case"].assignment_submissions.all()[0].review_form
        self.assertEqual(form.initial["status"], "approved")
        self.assertEqual(form.initial["feedback"], "Prima")

    # -- 3. context en geschiedenis -----------------------------------------
    def test_assignment_brief_is_shown_on_review_page(self):
        self.submit_answer("<p>Antwoord</p>")
        response = self.teacher_page()
        self.assertContains(response, "Opdracht bekijken")
        self.assertContains(response, "<p>Beschrijf <strong>de observatie</strong>.</p>", html=False)

    def test_each_review_stores_round_with_answer_snapshot(self):
        self.submit_answer("<p>Eerste versie</p>")
        self.review("resubmit", "Werk dit verder uit")
        self.submit_answer("<p>Tweede versie</p>")

        response = self.teacher_page()
        self.assertContains(response, "Antwoord bij vorige beoordeling")
        self.assertContains(response, "<p>Eerste versie</p>")
        self.assertContains(response, "<p>Tweede versie</p>")

        self.review("approved", "Nu volledig")
        rounds = list(self.submission.reviews.order_by("round"))
        self.assertEqual([r.round for r in rounds], [1, 2])
        self.assertEqual(rounds[0].answer, "<p>Eerste versie</p>")
        self.assertEqual(rounds[0].status, AssignmentSubmission.Status.RESUBMIT)
        self.assertEqual(rounds[1].answer, "<p>Tweede versie</p>")
        self.assertEqual(rounds[1].reviewer, self.teacher)

        response = self.teacher_page()
        self.assertContains(response, "Eerdere beoordelingen (1)")
        self.assertContains(response, "Werk dit verder uit")

        self.client.force_login(self.student)
        response = self.client.get(
            reverse("dossier:case_detail", args=[self.case.id]), {"assignment": self.submission.id}
        )
        self.assertContains(response, "Eerdere feedback (1)")
        self.assertContains(response, "Werk dit verder uit")
        self.assertContains(response, "Nu volledig")

    def test_previous_review_stays_visible_while_student_reworks(self):
        self.submit_answer("<p>Eerste versie</p>")
        self.review("resubmit", "Nog aanvullen")
        self.client.force_login(self.student)
        self.client.post(
            reverse("dossier:case_detail", args=[self.case.id]),
            {"assignment": self.submission.id, "answer": "<p>Concept</p>", "action": "save"},
        )
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, AssignmentSubmission.Status.TODO)
        response = self.teacher_page()
        self.assertContains(response, "Vorige beoordeling: Opnieuw inleveren")
        self.assertContains(response, "Nog aanvullen")
        self.assertContains(response, "De student werkt deze opdracht bij")

    def test_resubmit_reopens_student_case(self):
        self.submit_answer("<p>Antwoord</p>")
        StudentCase.objects.filter(pk=self.student_case.pk).update(status=StudentCase.Status.SUBMITTED)
        self.review("resubmit", "Opnieuw")
        self.student_case.refresh_from_db()
        self.assertEqual(self.student_case.status, StudentCase.Status.ACTIVE)

    # -- 4. modulefeedback en eindfeedback ----------------------------------
    def post_module_feedback(self, feedback, revision=False):
        self.client.force_login(self.teacher)
        data = {"feedback": feedback}
        if revision:
            data["revision_requested"] = "on"
        return self.client.post(
            reverse("dossier:teacher_module_feedback", args=[self.student_case.id, self.module.id]), data
        )

    def test_module_feedback_is_saved_audited_and_shown_to_student(self):
        response = self.post_module_feedback("<p>Vermeld ook de <strong>pariteit</strong>.</p>")
        self.assertRedirects(
            response,
            f"{reverse('dossier:teacher_student_case', args=[self.student_case.id])}#module-{self.module.id}",
            fetch_redirect_response=False,
        )
        self.module.refresh_from_db()
        self.assertEqual(self.module.feedback, "<p>Vermeld ook de <strong>pariteit</strong>.</p>")
        self.assertEqual(self.module.feedback_by, self.teacher)
        self.assertIsNotNone(self.module.feedback_at)
        self.assertFalse(self.module.revision_requested)
        self.assertTrue(AuditEvent.objects.filter(action="module_response.feedback").exists())

        self.client.force_login(self.student)
        response = self.client.get(reverse("dossier:dossier", args=[self.case.id]), {"module": self.module.id})
        self.assertContains(response, "Feedback docent")
        self.assertContains(response, "<strong>pariteit</strong>")

    def test_module_revision_request_reopens_dossier_until_resubmitted(self):
        self.submit_answer("<p>Antwoord</p>")
        self.client.force_login(self.student)
        self.client.post(reverse("dossier:submit_student_case", args=[self.case.id]))
        self.student_case.refresh_from_db()
        self.assertEqual(self.student_case.status, StudentCase.Status.SUBMITTED)

        self.post_module_feedback("Reden van opname ontbreekt", revision=True)
        self.student_case.refresh_from_db()
        self.module.refresh_from_db()
        self.assertTrue(self.module.revision_requested)
        self.assertEqual(self.student_case.status, StudentCase.Status.ACTIVE)

        # Goedkeuren van de opdracht sluit de studentversie niet af zolang
        # een gevraagde moduleaanpassing openstaat.
        self.review("approved", "")
        self.student_case.refresh_from_db()
        self.assertEqual(self.student_case.status, StudentCase.Status.ACTIVE)

        self.client.force_login(self.student)
        response = self.client.get(reverse("dossier:case_detail", args=[self.case.id]))
        self.assertContains(response, "Aanpassing gevraagd in het patiëntendossier")
        response = self.client.get(reverse("dossier:dossier", args=[self.case.id]), {"module": self.module.id})
        self.assertContains(response, "Je docent vraagt dit onderdeel aan te passen")

        self.client.post(reverse("dossier:submit_student_case", args=[self.case.id]))
        self.student_case.refresh_from_db()
        self.module.refresh_from_db()
        self.assertEqual(self.student_case.status, StudentCase.Status.SUBMITTED)
        self.assertFalse(self.module.revision_requested)

        # Feedback zonder nieuwe aanpassingsvraag rondt de ingediende versie af.
        self.post_module_feedback("Nu in orde")
        self.student_case.refresh_from_db()
        self.assertEqual(self.student_case.status, StudentCase.Status.REVIEWED)

    def test_module_feedback_does_not_close_unsubmitted_student_case(self):
        self.submit_answer("<p>Antwoord</p>")
        self.review("approved", "")
        StudentCase.objects.filter(pk=self.student_case.pk).update(status=StudentCase.Status.ACTIVE)
        self.post_module_feedback("Tussentijdse tip")
        self.student_case.refresh_from_db()
        self.assertEqual(self.student_case.status, StudentCase.Status.ACTIVE)

    def test_final_feedback_is_saved_and_shown_on_case_introduction(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("dossier:teacher_final_feedback", args=[self.student_case.id]),
            {"final_feedback": "<p>Mooi klinisch redeneren.</p><script>x()</script>"},
        )
        self.assertEqual(response.status_code, 302)
        self.student_case.refresh_from_db()
        self.assertEqual(self.student_case.final_feedback, "<p>Mooi klinisch redeneren.</p>")
        self.assertEqual(self.student_case.final_feedback_by, self.teacher)
        self.assertTrue(AuditEvent.objects.filter(action="student_case.final_feedback").exists())

        self.client.force_login(self.student)
        response = self.client.get(reverse("dossier:case_detail", args=[self.case.id]))
        self.assertContains(response, "Algemene feedback docent")
        self.assertContains(response, "Mooi klinisch redeneren.")

    def test_students_cannot_post_feedback(self):
        self.client.force_login(self.student)
        for url in (
            reverse("dossier:teacher_module_feedback", args=[self.student_case.id, self.module.id]),
            reverse("dossier:teacher_final_feedback", args=[self.student_case.id]),
        ):
            self.assertEqual(self.client.post(url, {"feedback": "x", "final_feedback": "x"}).status_code, 403)
        self.module.refresh_from_db()
        self.assertEqual(self.module.feedback, "")

    def test_feedback_views_reject_get(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("dossier:teacher_final_feedback", args=[self.student_case.id]))
        self.assertEqual(response.status_code, 403)
