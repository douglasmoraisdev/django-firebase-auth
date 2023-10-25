# Generated by Django 4.1.2 on 2023-10-25 09:19

import abstract_auth.abstract_user_profile
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SupabaseUserProfile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
            ],
            bases=(
                models.Model,
                abstract_auth.abstract_user_profile.AbstractUserProfile,
            ),
        ),
    ]
