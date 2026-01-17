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
	product = models.CharField(max_length=255)
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
	price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
	
	def __str__(self):
		return f"Stock {self.sl_no} - {self.product}"
	
	class Meta:
		verbose_name_plural = "Stock"

class Finance(models.Model):
	TRANSACTION_TYPES = [
		("DEBIT", "Debit"),
		("CREDIT", "Credit"),
	]

	REASON_CHOICES = [
		("DAILY_CHARGES", "Daily Charges"),
		("STOCK_IN_LOCAL", "Stock In Local"),
		("SERVICE_IN_LOCAL", "Service In Local"),
		("OTHER", "Other"),
	]
	
	sl_no = models.AutoField(primary_key=True)
	date = models.DateField()
	transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
	amount = models.DecimalField(max_digits=12, decimal_places=2)
	reason = models.CharField(max_length=255, choices=REASON_CHOICES, default="OTHER")
	description = models.TextField(blank=True, null=True)
	
	def __str__(self):
		return f"{self.transaction_type} - {self.amount} - {self.reason}"
	
	class Meta:
		verbose_name_plural = "Finance"


class Invoice(models.Model):
	PAYMENT_STATUS = [
		("UNPAID", "Unpaid"),
		("PAID", "Paid"),
	]
	
	invoice_no = models.CharField(max_length=50, unique=True)
	date = models.DateField()
	customer_name = models.CharField(max_length=120)
	mobile_num = models.CharField(max_length=15)
	customer_address = models.TextField(blank=True, null=True)
	discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
	gst = models.DecimalField("GST (%)", max_digits=5, decimal_places=2, default=Decimal("0.00"))
	total_amount = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=Decimal("0.00"))
	advance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
	balance = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=Decimal("0.00"))
	notes = models.TextField(blank=True, null=True)
	payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS, default="UNPAID")

	def __str__(self):
		return f"Invoice {self.invoice_no}"
	
	def calculate_subtotal(self):
		"""Calculate subtotal from line items (without item-level GST/discount)"""
		subtotal = Decimal("0.00")
		for item in self.items.all():
			subtotal += item.subtotal
		return subtotal
	
	def calculate_total_with_items(self):
		"""Calculate total including item-level GST and discounts"""
		total = Decimal("0.00")
		for item in self.items.all():
			total += item.total
		return total

	def save(self, *args, **kwargs):
		# Auto-generate invoice number if not set
		if not self.invoice_no:
			from datetime import datetime
			current_year = datetime.now().year
			# Get the count of invoices for this year
			year_prefix = f"INV-{current_year}-"
			last_invoice = Invoice.objects.filter(invoice_no__startswith=year_prefix).order_by('invoice_no').last()
			
			if last_invoice:
				# Extract the sequence number from last invoice
				last_seq = int(last_invoice.invoice_no.split('-')[-1])
				seq_number = last_seq + 1
			else:
				seq_number = 1
			
			self.invoice_no = f"{year_prefix}{seq_number:04d}"
		
		super().save(*args, **kwargs)
		# Calculate from items including their GST and discount
		item_total = self.calculate_total_with_items()
		# Apply invoice-level discount and GST if needed
		discounted = item_total - (self.discount or Decimal("0"))
		if discounted < 0:
			discounted = Decimal("0")
		gst_multiplier = Decimal("1") + ((self.gst or Decimal("0")) / Decimal("100"))
		self.total_amount = (discounted * gst_multiplier).quantize(Decimal("0.01"))
		self.balance = (self.total_amount - (self.advance_amount or Decimal("0"))).quantize(Decimal("0.01"))
		Invoice.objects.filter(pk=self.pk).update(total_amount=self.total_amount, balance=self.balance)

	class Meta:
		verbose_name_plural = "Invoices"


class InvoiceItem(models.Model):
	invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
	particulars = models.CharField(max_length=500)
	quantity = models.PositiveIntegerField(default=1)
	price = models.DecimalField(max_digits=12, decimal_places=2)
	discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
	gst = models.DecimalField("GST (%)", max_digits=5, decimal_places=2, default=Decimal("0.00"))
	
	def __str__(self):
		return f"{self.particulars} - {self.quantity} x ₹{self.price}"
	
	@property
	def subtotal(self):
		return self.quantity * self.price
	
	@property
	def total(self):
		base = self.quantity * self.price
		discounted = base - (self.discount or Decimal("0"))
		if discounted < 0:
			discounted = Decimal("0")
		gst_multiplier = Decimal("1") + ((self.gst or Decimal("0")) / Decimal("100"))
		return (discounted * gst_multiplier).quantize(Decimal("0.01"))
	
	class Meta:
		verbose_name_plural = "Invoice Items"


class Quotation(models.Model):
	sl_no = models.AutoField(primary_key=True)
	date = models.DateField()
	customer_name = models.CharField(max_length=120)
	mobile_num = models.CharField(max_length=15)
	customer_address = models.TextField(blank=True, null=True)
	discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
	gst = models.DecimalField("GST (%)", max_digits=5, decimal_places=2, default=Decimal("0.00"))
	total = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=Decimal("0.00"))
	notes = models.TextField(blank=True, null=True)

	def __str__(self):
		return f"Quotation {self.sl_no}"

	def calculate_subtotal(self):
		"""Calculate subtotal from line items"""
		subtotal = Decimal("0.00")
		for item in self.items.all():
			subtotal += item.subtotal
		return subtotal
	
	def calculate_total_with_items(self):
		"""Calculate total including item-level GST and discounts"""
		total = Decimal("0.00")
		for item in self.items.all():
			total += item.total
		return total

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		# Calculate from items including their GST and discount
		item_total = self.calculate_total_with_items()
		# Apply quotation-level discount and GST if needed
		discounted = item_total - (self.discount or Decimal("0"))
		if discounted < 0:
			discounted = Decimal("0")
		gst_multiplier = Decimal("1") + ((self.gst or Decimal("0")) / Decimal("100"))
		self.total = (discounted * gst_multiplier).quantize(Decimal("0.01"))
		Quotation.objects.filter(pk=self.pk).update(total=self.total)

	class Meta:
		verbose_name_plural = "Quotations"


class QuotationItem(models.Model):
	quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='items')
	particulars = models.CharField(max_length=500)
	quantity = models.PositiveIntegerField(default=1)
	price = models.DecimalField(max_digits=12, decimal_places=2)
	discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
	gst = models.DecimalField("GST (%)", max_digits=5, decimal_places=2, default=Decimal("0.00"))
	
	def __str__(self):
		return f"{self.particulars} - {self.quantity} x ₹{self.price}"
	
	@property
	def subtotal(self):
		return self.quantity * self.price
	
	@property
	def total(self):
		base = self.quantity * self.price
		discounted = base - (self.discount or Decimal("0"))
		if discounted < 0:
			discounted = Decimal("0")
		gst_multiplier = Decimal("1") + ((self.gst or Decimal("0")) / Decimal("100"))
		return (discounted * gst_multiplier).quantize(Decimal("0.01"))
	
	class Meta:
		verbose_name_plural = "Quotation Items"
