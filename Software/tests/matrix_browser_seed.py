"""Seed ONLY the disposable epd_matrix database for matrix-browser.mjs.

Run with manage.py shell, after migrating a new isolated test database.
"""
import json
import os

from django.conf import settings
from dossier.test_matrix import MatrixWorkflowTests
from dossier.matrix import legacy_definition
from dossier.models import LibraryField

if not settings.DEBUG or settings.DATABASES["default"]["NAME"] != "epd_matrix":
    raise RuntimeError("Browser fixtures are restricted to the disposable epd_matrix database.")
password = os.environ["EPD_BROWSER_TEST_PASSWORD"]
MatrixWorkflowTests.setUpTestData()
fixtures = MatrixWorkflowTests
for user in (fixtures.teacher, fixtures.admin, fixtures.student):
    user.set_password(password)
    user.save()
large = LibraryField.objects.create(template=fixtures.template, key="large-grid", label="Maximum raster", field_type="matrix", matrix_definition=legacy_definition([str(i + 1) for i in range(100)], [str(i + 1) for i in range(20)]))
print(json.dumps({"case": fixtures.case.pk, "module": fixtures.module.pk, "template": fixtures.template.pk, "field": fixtures.field.pk, "student_case": fixtures.student_case.pk, "large": large.pk}))
