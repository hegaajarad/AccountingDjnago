from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("cashbox", "0002_cashbox_name"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="cashbox",
            unique_together=set(),
        ),
    ]
