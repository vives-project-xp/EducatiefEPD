from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils.text import slugify


def backfill_education(apps, schema_editor):
    Education = apps.get_model("dossier", "Education")
    Case = apps.get_model("dossier", "Case")
    Profile = apps.get_model("dossier", "Profile")
    LibraryTemplate = apps.get_model("dossier", "LibraryTemplate")

    def resolve(name):
        name = name.strip() or "Vroedkunde"
        existing = Education.objects.filter(name=name).first()
        if existing:
            return existing
        base = slugify(name)[:110] or "opleiding"
        candidate = base
        number = 2
        while Education.objects.filter(slug=candidate).exists():
            candidate = f"{base[:105]}-{number}"
            number += 1
        return Education.objects.create(name=name, slug=candidate)

    default = resolve("Vroedkunde")
    Case.objects.filter(education_new__isnull=True).update(education_new=default)
    for profile in Profile.objects.exclude(education=""):
        profile.education_new = resolve(profile.education)
        profile.save(update_fields=["education_new"])
    for template in LibraryTemplate.objects.exclude(education=""):
        template.education_new = resolve(template.education)
        template.save(update_fields=["education_new"])


class Migration(migrations.Migration):
    dependencies = [
        ("dossier", "0004_alter_assignmentsubmission_options_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Education",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("slug", models.SlugField(max_length=120, unique=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="ExternalIdentity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("issuer", models.URLField(max_length=255)),
                ("subject", models.CharField(max_length=255)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="external_identities", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="externalidentity",
            constraint=models.UniqueConstraint(fields=("issuer", "subject"), name="unique_external_identity"),
        ),
        migrations.CreateModel(
            name="TeachingGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("education", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="groups", to="dossier.education")),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="teaching_groups", to=settings.AUTH_USER_MODEL)),
                ("members", models.ManyToManyField(blank=True, related_name="epd_teaching_groups", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["education__name", "name"]},
        ),
        migrations.AddConstraint(
            model_name="teachinggroup",
            constraint=models.UniqueConstraint(fields=("education", "teacher", "name"), name="unique_teaching_group_name"),
        ),
        migrations.AddField(
            model_name="case",
            name="education_new",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="cases", to="dossier.education"),
        ),
        migrations.AddField(
            model_name="case",
            name="allowed_groups",
            field=models.ManyToManyField(blank=True, related_name="cases", to="dossier.teachinggroup"),
        ),
        migrations.AddField(
            model_name="profile",
            name="education_new",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="profiles", to="dossier.education"),
        ),
        migrations.AddField(
            model_name="librarytemplate",
            name="education_new",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="templates", to="dossier.education"),
        ),
        migrations.RunPython(backfill_education, migrations.RunPython.noop),
        migrations.RemoveField(model_name="profile", name="education"),
        migrations.RemoveField(model_name="librarytemplate", name="education"),
        migrations.RenameField(model_name="profile", old_name="education_new", new_name="education"),
        migrations.RenameField(model_name="librarytemplate", old_name="education_new", new_name="education"),
        migrations.RenameField(model_name="case", old_name="education_new", new_name="education"),
        migrations.AlterField(
            model_name="case", name="education",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cases", to="dossier.education"),
        ),
        migrations.AlterField(model_name="librarytemplate", name="is_fixed", field=models.BooleanField(default=False)),
    ]
