
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('admins', '0023_batch_batch_overview_batch_course_duration_months_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE admins_subject
                DROP COLUMN IF EXISTS subject_demo_url;

                ALTER TABLE admins_subject
                DROP COLUMN IF EXISTS subject_demo_video;
            """,
            reverse_sql="""
                ALTER TABLE admins_subject
                ADD COLUMN subject_demo_url VARCHAR(255) NOT NULL DEFAULT '';

                ALTER TABLE admins_subject
                ADD COLUMN subject_demo_video VARCHAR(255) NULL;
            """,
        ),
    ]
