import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizer", "0005_muelecourse"),
    ]

    operations = [
        migrations.CreateModel(
            name="ResourceRecommendation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subject_code", models.CharField(blank=True, max_length=32)),
                ("theme", models.CharField(max_length=140)),
                ("source_type", models.CharField(choices=[("youtube", "YouTube"), ("book", "Book"), ("article", "Article")], max_length=16)),
                ("title", models.CharField(max_length=220)),
                ("query", models.CharField(max_length=260)),
                ("url", models.URLField(max_length=1024)),
                ("reason", models.CharField(blank=True, max_length=280)),
                ("score", models.PositiveIntegerField(default=0)),
                ("status", models.CharField(choices=[("suggested", "Suggested"), ("saved", "Saved"), ("dismissed", "Dismissed"), ("opened", "Opened")], default="suggested", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="resource_recommendations", to="organizer.profile")),
            ],
            options={
                "ordering": ["status", "-score", "-updated_at"],
                "unique_together": {("profile", "subject_code", "source_type", "query")},
                "indexes": [
                    models.Index(fields=["profile", "status", "-score"], name="organizer_r_profile_67621a_idx"),
                    models.Index(fields=["profile", "subject_code", "source_type"], name="organizer_r_profile_bd33cc_idx"),
                ],
            },
        ),
    ]
