from decimal import Decimal
from django.db import models

class Entry(models.Model):
	STATUS_CHOICES = [
		("IN", "In"),
		("OUT", "Out"),
		("SCRAP", "Scrap"),
	]
	
	sl_no = models.AutoField(primary_key=True)
	date = models.DateField()
	customer_name = models.CharField(max_length=100)
	mobile_num = models.CharField(max_length=15)
	product_issue = models.CharField(max_length=255)
	product_with = models.CharField(max_length=255)
	address = models.TextField()
	product_status = models.CharField(max_length=10, choices=STATUS_CHOICES)
	
	def __str__(self):
		return f"Entry {self.sl_no} - {self.customer_name}"
	
	class Meta:
		verbose_name_plural = "Entries"

class Stock(models.Model):
	sl_no = models.AutoField(primary_key=True)
	date = models.DateField()
	product = models.CharField(max_length=255)
	serial_number = models.CharField(max_length=100, blank=True, null=True)
	quantity = models.PositiveIntegerField(default=1)
	
	def __str__(self):
		return f"Stock {self.sl_no} - {self.product}"
	
	class Meta:
		verbose_name_plural = "Stock"

class Finance(models.Model):
	TRANSACTION_TYPES = [
		("DEBIT", "Debit"),
		("CREDIT", "Credit"),
	]
	
	DEBIT_REASON_CHOICES = [
		("DAILY_CHARGES", "Daily Charges"),
		("STOCK_IN_LOCAL", "Stock In Local"),
		("SERVICE_IN_LOCAL", "Service In Local"),
		("OTHER", "Other"),
	]
	
	sl_no = models.AutoField(primary_key=True)
	date = models.DateField()
	transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
	amount = models.DecimalField(max_digits=12, decimal_places=2)
	reason = models.CharField(max_length=255)
	description = models.TextField(blank=True, null=True)
	
	def __str__(self):
		return f"{self.transaction_type} - {self.amount} - {self.reason}"
	
	class Meta:
		verbose_name_plural = "Finance"


class Invoice(models.Model):
	invoice_no = models.CharField(max_length=50, unique=True)
	date = models.DateField()
	customer_name = models.CharField(max_length=120)
	mobile_num = models.CharField(max_length=15)
	particulars = models.TextField()
	quantity = models.PositiveIntegerField(default=1)
	price = models.DecimalField(max_digits=12, decimal_places=2)
	discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
	gst = models.DecimalField("GST (%)", max_digits=5, decimal_places=2, default=Decimal("0.00"))
	total_amount = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=Decimal("0.00"))
	advance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
	balance = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=Decimal("0.00"))

	def __str__(self):
		return f"Invoice {self.invoice_no}"

	def save(self, *args, **kwargs):
		base = Decimal(self.quantity) * (self.price or Decimal("0"))
		discounted = base - (self.discount or Decimal("0"))
		if discounted < 0:
			discounted = Decimal("0")
		gst_multiplier = Decimal("1") + ((self.gst or Decimal("0")) / Decimal("100"))
		self.total_amount = (discounted * gst_multiplier).quantize(Decimal("0.01"))
		self.balance = (self.total_amount - (self.advance_amount or Decimal("0"))).quantize(Decimal("0.01"))
		super().save(*args, **kwargs)

	class Meta:
		verbose_name_plural = "Invoices"


class Quotation(models.Model):
	sl_no = models.AutoField(primary_key=True)
	date = models.DateField()
	customer_name = models.CharField(max_length=120)
	mobile_num = models.CharField(max_length=15)
	particulars = models.TextField()
	quantity = models.PositiveIntegerField(default=1)
	price = models.DecimalField(max_digits=12, decimal_places=2)
	total = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=Decimal("0.00"))

	def __str__(self):
		return f"Quotation {self.sl_no}"

	def save(self, *args, **kwargs):
		base = Decimal(self.quantity) * (self.price or Decimal("0"))
		self.total = base.quantize(Decimal("0.01"))
		super().save(*args, **kwargs)

	class Meta:
		verbose_name_plural = "Quotations"
