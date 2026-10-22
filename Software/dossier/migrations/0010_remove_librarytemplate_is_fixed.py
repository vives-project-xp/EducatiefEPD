from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("dossier", "0009_merge_dossiers_functions")]

    operations = [
        migrations.RemoveField(model_name="librarytemplate", name="is_fixed"),
    ]
