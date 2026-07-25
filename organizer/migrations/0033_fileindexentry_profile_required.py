import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """profile becomes required on FileIndexEntry: SQLite's UNIQUE
    constraint treats every NULL as distinct from every other NULL, so
    unique_together on (profile, path) silently allowed duplicate rows
    the moment profile was ever None. Confirmed zero real installs have
    hit this yet (FileIndexEntry only shipped this session, and the real
    project database has zero rows in this table), so there's no data to
    migrate -- this is a straight tightening, not a backfill.
    """

    dependencies = [
        ('organizer', '0032_moveevent_drive_backup_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fileindexentry',
            name='profile',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='file_index_entries',
                to='organizer.profile',
            ),
        ),
    ]
