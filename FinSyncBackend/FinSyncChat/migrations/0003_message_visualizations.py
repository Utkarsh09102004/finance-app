from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('FinSyncChat', '0002_alter_chatsettings_preferred_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='visualizations',
            field=models.JSONField(blank=True, help_text='Chart specifications associated with this assistant message', null=True),
        ),
    ]
