# Generated manually to add connection_type field

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("social", "0002_initial_standalone_setup"),
    ]

    operations = [
        migrations.AddField(
            model_name="socialaccount",
            name="connection_type",
            field=models.CharField(
                choices=[
                    ("standard", "Standard"),
                    ("facebook_business", "Facebook Business"),
                    ("instagram_direct", "Instagram Direct"),
                ],
                default="standard",
                max_length=20,
            ),
        ),
    ]