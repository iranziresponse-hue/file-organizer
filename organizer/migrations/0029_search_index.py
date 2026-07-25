from django.db import migrations

# FTS5 virtual table backing organizer.core.search_index. Not a normal
# Django model -- no managed model class, only raw SQL via
# django.db.connection.cursor() in organizer/core/search_index.py. record_id
# and profile_id are UNINDEXED (looked up, never searched by text); title/
# body are the actual full-text-searched columns.
CREATE_SQL = (
    "CREATE VIRTUAL TABLE search_index USING fts5("
    "record_type, record_id UNINDEXED, profile_id UNINDEXED, title, body)"
)
DROP_SQL = "DROP TABLE IF EXISTS search_index"


class Migration(migrations.Migration):

    dependencies = [
        ('organizer', '0028_backgroundtask'),
    ]

    operations = [
        migrations.RunSQL(sql=CREATE_SQL, reverse_sql=DROP_SQL),
    ]
