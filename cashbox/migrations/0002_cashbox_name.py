from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cashbox", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="cashbox",
            name="name",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
