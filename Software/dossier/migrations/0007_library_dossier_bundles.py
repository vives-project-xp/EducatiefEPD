import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dossier", "0006_library_template_seed_key"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LibraryDossier",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("title", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Actief"), ("archived", "Gearchiveerd")],
                        default="active",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="library_dossiers",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "education",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="library_dossiers",
                        to="dossier.education",
                    ),
                ),
            ],
            options={"ordering": ["title"]},
        ),
        migrations.CreateModel(
            name="LibraryDossierModule",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("position", models.PositiveIntegerField(default=0)),
                (
                    "dossier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="module_entries",
                        to="dossier.librarydossier",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="dossier_entries",
                        to="dossier.librarytemplate",
                    ),
                ),
            ],
            options={"ordering": ["position", "id"]},
        ),
        migrations.AddConstraint(
            model_name="librarydossiermodule",
            constraint=models.UniqueConstraint(
                fields=("dossier", "template"), name="unique_dossier_library_template"
            ),
        ),
        migrations.AddField(
            model_name="librarydossier",
            name="modules",
            field=models.ManyToManyField(
                related_name="dossiers",
                through="dossier.LibraryDossierModule",
                to="dossier.librarytemplate",
            ),
        ),
    ]
