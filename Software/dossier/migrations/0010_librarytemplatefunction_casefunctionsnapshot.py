from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("dossier", "0009_merge_dossiers_functions"),
    ]

    operations = [
        migrations.CreateModel(
            name="LibraryTemplateFunction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("function", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="template_links", to="dossier.functiondefinition")),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="function_links", to="dossier.librarytemplate")),
            ],
            options={"ordering": ["position", "id"]},
        ),
        migrations.CreateModel(
            name="CaseFunctionSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("kind", models.CharField(max_length=16)),
                ("position", models.PositiveIntegerField(default=0)),
                ("definition", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("module", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="function_snapshots", to="dossier.module")),
            ],
            options={"ordering": ["position", "id"]},
        ),
        migrations.AddConstraint(
            model_name="librarytemplatefunction",
            constraint=models.UniqueConstraint(fields=("template", "function"), name="unique_library_template_function"),
        ),
    ]
