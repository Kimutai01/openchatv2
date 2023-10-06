# Generated by Django 4.2 on 2023-08-10 12:35

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("experiments", "0025_alter_experimentsession_chat"),
    ]

    operations = [
        migrations.CreateModel(
            name="NoActivityMessageConfig",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "message_for_bot",
                    models.CharField(help_text="This message will be sent to the LLM along with the message history"),
                ),
                ("name", models.CharField(max_length=64)),
                ("max_pings", models.IntegerField()),
                (
                    "ping_after",
                    models.IntegerField(help_text="The amount of minutes after which to ping the user. Minimum 1."),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="experiment",
            name="no_activity_config",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="experiments.noactivitymessageconfig",
            ),
        ),
    ]