# Generated for NeoLearner My Profile fields.
# Review against the current students/models.py before applying.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0009_quizattempt_quizattemptanswer_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentprofile",
            name="alternate_phone",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[
                    ("female", "Female"),
                    ("male", "Male"),
                    ("other", "Other"),
                    ("prefer_not_to_say", "Prefer not to say"),
                ],
                default="",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="date_of_birth",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="identity_photo",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="identity_photo_public_id",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="guardian_full_name",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="guardian_relationship",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="guardian_phone",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="guardian_alternate_phone",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="guardian_email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="study_work_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("studying", "Studying"),
                    ("working", "Working"),
                    ("both", "Studying and Working"),
                    ("other", "Other"),
                ],
                default="",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="institution_or_workplace",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="education_qualification",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="course_or_field",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="address_house_street",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="address_locality",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="address_city",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="address_district",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="address_state",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="address_pin_code",
            field=models.CharField(blank=True, default="", max_length=12),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="address_country",
            field=models.CharField(blank=True, default="India", max_length=100),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="learning_goals",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="interested_exams_courses",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="profile_completed",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="profile_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]