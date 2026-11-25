# Generated for NeoLearner Edit Batch demo title length update.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("admins", "0025_batch_demo_mode_subjectdemo"),
    ]

    operations = [
        migrations.AlterField(
            model_name="batchdemo",
            name="title",
            field=models.CharField(max_length=150),
        ),
        migrations.AlterField(
            model_name="subjectdemo",
            name="title",
            field=models.CharField(max_length=150),
        ),
    ]