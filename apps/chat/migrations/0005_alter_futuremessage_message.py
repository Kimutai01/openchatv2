# Generated by Django 4.2 on 2023-10-06 11:07

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0004_futuremessage"),
    ]

    operations = [
        migrations.AlterField(
            model_name="futuremessage",
            name="message",
            field=models.CharField(max_length=1000),
        ),
    ]
