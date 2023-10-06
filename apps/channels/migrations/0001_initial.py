# Generated by Django 4.2 on 2023-06-20 13:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("experiments", "0022_consentform_experiment_consent_form"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExperimentChannel",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(help_text="The name of this channel", max_length=40)),
                ("active", models.BooleanField(default=True)),
                ("extra_data", models.JSONField(default=dict)),
                (
                    "experiment",
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="experiments.experiment"
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
