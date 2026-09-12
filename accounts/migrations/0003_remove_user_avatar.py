from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_otp_sent_to_user_welcome_email_sent_at_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="avatar",
        ),
    ]
