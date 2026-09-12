from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assistant", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="meta",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
