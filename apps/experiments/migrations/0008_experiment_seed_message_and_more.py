# Generated by Django 4.2 on 2023-04-19 13:20

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("experiments", "0007_prompt_input_formatter_alter_prompt_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="experiment",
            name="seed_message",
            field=models.TextField(
                blank=True,
                default="",
                help_text="If set, send this message to the bot when the session starts, and prompt the user with the initial response.",
            ),
        ),
        migrations.AddField(
            model_name="experimentsession",
            name="seed_task_id",
            field=models.CharField(
                blank=True, default="", help_text="System ID of the seed message task, if present.", max_length=40
            ),
        ),
    ]