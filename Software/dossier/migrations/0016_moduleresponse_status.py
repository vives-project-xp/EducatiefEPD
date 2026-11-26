from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dossier', '0015_alter_moduleresponse_created_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='moduleresponse',
            name='status',
            field=models.CharField(
                choices=[('concept', 'Concept'), ('published', 'Gepubliceerd')],
                default='concept',
                max_length=16,
            ),
        ),
    ]
