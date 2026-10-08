import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("dossier", "0007_library_dossier_bundles")]

    operations = [
        migrations.AddField(
            model_name="librarydossier",
            name="copied_from",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="copies",
                to="dossier.librarydossier",
            ),
        ),
    ]
