"""Create disposable browser fixtures, only in the isolated main test database."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client
from dossier.models import FunctionDefinition, ManagedForm, ManagedQuestion, Profile
from dossier.services import ensure_default_templates

if settings.DATABASES["default"]["NAME"] != "epd_main_test":
    raise RuntimeError("Browser fixtures require the disposable epd_main_test database.")

call_command("migrate", verbosity=0)
ensure_default_templates()
user = get_user_model().objects.create_user("main-browser-teacher")
user.epd_profile.role = Profile.Role.TEACHER
user.epd_profile.save()
function = FunctionDefinition.objects.create(title="Browser intake", kind=FunctionDefinition.Kind.GROUP)
form = ManagedForm.objects.create(function=function, title="Intakeformulier")
ManagedQuestion.objects.create(
    form=form, field_type=ManagedQuestion.FieldType.MULTIPLE_CHOICE,
    question="Kies één antwoord", options=["Antwoord A", "Antwoord B", "Antwoord C"],
)
client = Client()
client.force_login(user)
Path(sys.argv[1]).write_text(json.dumps({
    "session": client.cookies[settings.SESSION_COOKIE_NAME].value,
    "functionId": function.pk,
}), encoding="utf-8")
print("Disposable browser fixtures ready.")
