
from django.db import models

class FinanceTransaction(models.Model):
	TRANSACTION_TYPES = [
		("CREDIT", "Credit"),
		("DEBIT", "Debit"),
	]
	amount = models.DecimalField(max_digits=12, decimal_places=2)
	transaction_type = models.CharField(max_length=6, choices=TRANSACTION_TYPES)
	reason = models.CharField(max_length=255)
	date = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"{self.transaction_type} - {self.amount} ({self.reason})"


class Product(models.Model):
	name = models.CharField(max_length=100)
	description = models.TextField(blank=True)

	def __str__(self):
		return self.name

class InventoryTransaction(models.Model):
	TRANSACTION_TYPES = [
		("IN", "Stock In"),
		("OUT", "Stock Out"),
	]
	product = models.ForeignKey(Product, on_delete=models.CASCADE)
	transaction_type = models.CharField(max_length=3, choices=TRANSACTION_TYPES)
	quantity = models.PositiveIntegerField()
	date = models.DateTimeField(auto_now_add=True)
	note = models.CharField(max_length=255, blank=True)

	def __str__(self):
		return f"{self.product.name} - {self.transaction_type} - {self.quantity}"

	def save(self, *args, **kwargs):
		# Only allow OUT if enough stock
		if self.transaction_type == "OUT":
			current_stock = InventoryTransaction.get_current_stock(self.product)
			if self.quantity > current_stock:
				raise ValueError("Not enough stock for this transaction.")
		super().save(*args, **kwargs)

	@staticmethod
	def get_current_stock(product):
		in_qty = InventoryTransaction.objects.filter(product=product, transaction_type="IN").aggregate(models.Sum("quantity"))["quantity__sum"] or 0
		out_qty = InventoryTransaction.objects.filter(product=product, transaction_type="OUT").aggregate(models.Sum("quantity"))["quantity__sum"] or 0
		return in_qty - out_qty
