"""Create disposable fixtures for feedback-browser.mjs, only in the isolated feedback test database."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client
from dossier.models import (
    Assignment, AssignmentSubmission, Case, Education, LibraryField, LibraryTemplate,
    Patient, Profile, TeachingGroup,
)
from dossier.services import copy_template_to_case, start_student_case

if settings.DATABASES["default"]["NAME"] != "epd_feedback_test":
    raise RuntimeError("Browser fixtures require the disposable epd_feedback_test database.")

call_command("migrate", verbosity=0)
users = get_user_model().objects
education = Education.objects.get(slug="vroedkunde")
teacher = users.create_user("feedback-browser-teacher")
teacher.epd_profile.role = Profile.Role.TEACHER
teacher.epd_profile.education = education
teacher.epd_profile.save()
student = users.create_user("feedback-browser-student")
student.epd_profile.education = education
student.epd_profile.save()
patient = Patient.objects.create(name="Feedback, Fien", reference="FB-1", created_by=teacher)
case = Case.objects.create(
    title="Feedbackcasus", patient=patient, education=education, course="Vroedkunde",
    introduction="Inleiding", created_by=teacher, status=Case.Status.PUBLISHED,
)
group = TeachingGroup.objects.create(name="Feedbackgroep", education=education, teacher=teacher)
group.members.add(student)
case.allowed_groups.add(group)
template = LibraryTemplate.objects.create(title="Anamnese", category="questionnaire", theme="Opname", education=education)
LibraryField.objects.create(template=template, label="Reden van opname", key="reden", field_type="long_text", position=0)
copy_template_to_case(template, case)
Assignment.objects.create(case=case, phase="Opdracht 1", title="Observeer", content="<p>Beschrijf de observatie.</p>", position=1)
student_case, _ = start_student_case(case, student)
submission = student_case.assignment_submissions.get()
# Unsafe legacy answer written straight to the database, as was possible before sanitizing on save.
AssignmentSubmission.objects.filter(pk=submission.pk).update(
    answer='<p>Temperatuur <span style="color: #e03e2d;">38,5</span></p>'
           '<img src="x" onerror="window.__xss = 1"><script>window.__xss = 2</script>',
    status=AssignmentSubmission.Status.SUBMITTED,
)


def session(user):
    client = Client()
    client.force_login(user)
    return client.cookies[settings.SESSION_COOKIE_NAME].value


Path(sys.argv[1]).write_text(json.dumps({
    "teacher": session(teacher), "student": session(student),
    "caseId": case.pk, "studentCaseId": student_case.pk,
    "submissionId": submission.pk, "moduleId": student_case.module_responses.get().pk,
}), encoding="utf-8")
print("Disposable feedback browser fixtures ready.")
