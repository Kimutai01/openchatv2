# Generated by Django 4.1.7 on 2023-04-12 12:05

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("experiments", "0005_alter_experiment_source_material"),
    ]

    operations = [
        migrations.AddField(
            model_name="experiment",
            name="llm",
            field=models.CharField(
                choices=[("gpt-3.5-turbo", "GPT 3.5 (Chat GPT)"), ("gpt-4", "GPT 4")],
                default="gpt-3.5-turbo",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="experimentsession",
            name="llm",
            field=models.CharField(
                choices=[("gpt-3.5-turbo", "GPT 3.5 (Chat GPT)"), ("gpt-4", "GPT 4")],
                default="gpt-3.5-turbo",
                max_length=20,
            ),
        ),
    ]
