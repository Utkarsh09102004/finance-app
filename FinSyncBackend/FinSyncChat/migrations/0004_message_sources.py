from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('FinSyncChat', '0003_message_visualizations'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='sources',
            field=models.JSONField(blank=True, help_text='Tool output sources referenced in this assistant message', null=True),
        ),
    ]
