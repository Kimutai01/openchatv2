# Generated by Django 4.2 on 2023-10-06 12:26

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userapikey",
            name="name",
            field=models.CharField(
                default=None,
                help_text="A free-form name for the API key. Need not be unique. 50 characters max.",
                max_length=50,
            ),
        ),
    ]
