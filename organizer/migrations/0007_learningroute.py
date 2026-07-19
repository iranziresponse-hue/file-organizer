import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizer", "0006_resourcerecommendation"),
    ]

    operations = [
        migrations.CreateModel(
            name="LearningRoute",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subject_code", models.CharField(max_length=32)),
                ("theme", models.CharField(max_length=140)),
                ("title", models.CharField(max_length=220)),
                ("steps", models.JSONField(blank=True, default=list)),
                ("status", models.CharField(choices=[("planned", "Planned"), ("active", "Active"), ("done", "Done"), ("paused", "Paused")], default="planned", max_length=16)),
                ("current_step", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="learning_routes", to="organizer.profile")),
                ("recommendation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="learning_routes", to="organizer.resourcerecommendation")),
            ],
            options={
                "ordering": ["status", "subject_code", "-updated_at"],
                "unique_together": {("profile", "subject_code", "theme")},
                "indexes": [
                    models.Index(fields=["profile", "status", "subject_code"], name="organizer_l_profile_f4778c_idx"),
                ],
            },
        ),
    ]
