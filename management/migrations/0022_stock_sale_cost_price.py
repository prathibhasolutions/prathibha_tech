from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('management', '0021_auditevent'),
    ]

    operations = [
        migrations.RenameField(
            model_name='stock',
            old_name='price',
            new_name='sale_price',
        ),
        migrations.AddField(
            model_name='stock',
            name='cost_price',
            field=models.DecimalField(max_digits=12, decimal_places=2, default=0),
        ),
    ]
