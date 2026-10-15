
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0014_remove_legacy_refund_number_column'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE orders_refund "
                "DROP COLUMN IF EXISTS refund_number;"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
