from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0026_alter_finance_reason"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceBooking",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "service_needed",
                    models.CharField(
                        choices=[
                            ("HARDWARE_SERVICES", "Hardware Services"),
                            ("PRINTER_SERVICES", "Printer Services"),
                            ("CARTRIDGE_REFILLING", "Cartridge Refilling"),
                            ("CHIP_LEVEL_SERVICES", "Chip Level Services"),
                            ("NETWORKING", "Networking"),
                            ("AMC_SERVICES", "AMC Services"),
                            ("CC_CAMERA_SERVICES", "CC Camera Services"),
                            ("DATA_RECOVERY", "Data Recovery"),
                        ],
                        max_length=40,
                    ),
                ),
                ("mobile_num", models.CharField(max_length=15)),
                ("address", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Service Booking",
                "verbose_name_plural": "Service Bookings",
                "ordering": ["-created_at"],
            },
        ),
    ]
