from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0008_merge_20260929_1723"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="refundattempt",
            options={"ordering": ["attempt_number", "created_at"]},
        ),

        migrations.RenameField(
            model_name="refundattempt",
            old_name="processed_at",
            new_name="completed_at",
        ),

        migrations.RenameField(
            model_name="refundattempt",
            old_name="started_at",
            new_name="created_at",
        ),

        migrations.RenameField(
            model_name="refundattempt",
            old_name="requested_amount",
            new_name="amount",
        ),

        migrations.RenameIndex(
            model_name="refundattempt",
            new_name="refund_att_refund_status_idx",
            old_name="refund_att_status_idx",
        ),

        migrations.RemoveField(
            model_name="refund",
            name="refund_number",
        ),

        migrations.RemoveField(
            model_name="refundattempt",
            name="admin_note",
        ),

        migrations.RemoveField(
            model_name="refundattempt",
            name="refunded_amount",
        ),

        migrations.AddField(
            model_name="refundattempt",
            name="gateway_response",
            field=models.JSONField(
                blank=True,
                null=True,
            ),
        ),

        migrations.AddField(
            model_name="refundattempt",
            name="razorpay_payment_id",
            field=models.CharField(
                blank=True,
                max_length=100,
                null=True,
            ),
        ),

        migrations.AlterField(
            model_name="refundattempt",
            name="razorpay_refund_id",
            field=models.CharField(
                blank=True,
                max_length=100,
                null=True,
            ),
        ),

        migrations.AlterField(
            model_name="refundattempt",
            name="status",
            field=models.CharField(
                choices=[
                    ("initiated", "Initiated"),
                    ("success", "Success"),
                    ("failed", "Failed"),
                ],
                db_index=True,
                default="initiated",
                max_length=20,
            ),
        ),
    ]