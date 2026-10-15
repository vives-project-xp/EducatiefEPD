import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dossier", "0007_librarytemplate_functions"),
    ]

    operations = [
        migrations.CreateModel(
            name="FunctionDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("kind", models.CharField(choices=[("formulier", "Formulier"), ("groep", "Formulierengroep")], max_length=16)),
                ("std", models.BooleanField(default=False)),
                ("locked", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["title", "id"]},
        ),
        migrations.CreateModel(
            name="ManagedForm",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, max_length=180)),
                ("position", models.PositiveIntegerField(default=0)),
                ("function", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="forms", to="dossier.functiondefinition")),
            ],
            options={"ordering": ["position", "id"]},
        ),
        migrations.CreateModel(
            name="ManagedQuestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField(default=0)),
                ("field_type", models.CharField(choices=[("image", "Afbeelding weergeven"), ("link", "Hyperlink"), ("info", "Toelichting"), ("imageUpload", "Afbeelding uploaden"), ("fileUpload", "Bestand uploaden"), ("date", "Datum"), ("dateTime", "Datum en tijd"), ("number", "Getal"), ("matrix", "Matrix (maximaal 2)"), ("multipleChoice", "Meerkeuze"), ("text", "Tekst"), ("time", "Tijd")], default="text", max_length=24)),
                ("question", models.CharField(blank=True, max_length=500)),
                ("unit", models.CharField(blank=True, max_length=120)),
                ("required", models.BooleanField(default=False)),
                ("options", models.JSONField(blank=True, default=list)),
                ("columns", models.JSONField(blank=True, default=list)),
                ("rows", models.JSONField(blank=True, default=list)),
                ("url", models.URLField(blank=True, max_length=1000)),
                ("button_text", models.CharField(blank=True, max_length=180)),
                ("image", models.TextField(blank=True)),
                ("caption", models.CharField(blank=True, max_length=280)),
                ("explanation", models.TextField(blank=True)),
                ("form", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="questions", to="dossier.managedform")),
            ],
            options={"ordering": ["position", "id"]},
        ),
        migrations.AddIndex(
            model_name="functiondefinition",
            index=models.Index(fields=["deleted_at", "created_at"], name="fn_del_created_idx"),
        ),
    ]