import dossier.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dossier", "0017_merge_dossier_heads"),
    ]

    operations = [
        migrations.AlterField(
            model_name="patient",
            name="image",
            field=models.ImageField(blank=True, max_length=240, upload_to=dossier.models.patient_image_path),
        ),
    ]
