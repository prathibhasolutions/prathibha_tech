
from django.contrib import admin
from django.urls import path, reverse
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.contrib.admin import AdminSite
from .models import Product, InventoryTransaction, FinanceTransaction

@admin.register(FinanceTransaction)
class FinanceTransactionAdmin(admin.ModelAdmin):
	list_display = ("transaction_type", "amount", "reason", "date")
	list_filter = ("transaction_type", "date")
	search_fields = ("reason",)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
	list_display = ("name", "description")
	search_fields = ("name",)

@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
	list_display = ("product", "transaction_type", "quantity", "date", "note")
	list_filter = ("transaction_type", "date")
	search_fields = ("product__name", "note")


# Custom admin view for current stock
from django.urls import reverse
from django.utils.html import format_html
from django.contrib.admin import AdminSite

def current_stock_view(request):
	from .models import Product, InventoryTransaction
	products = Product.objects.all()
	stock_data = []
	for product in products:
		stock = InventoryTransaction.get_current_stock(product)
		stock_data.append({
			'product': product,
			'stock': stock
		})
	context = dict(
		admin.site.each_context(request),
		stock_data=stock_data,
	)
	return TemplateResponse(request, "admin/current_stock.html", context)

def custom_admin_urls(urls):
	def get_urls():
		custom = [
			path('current-stock/', admin.site.admin_view(current_stock_view), name='current-stock'),
		]
		return custom + urls
	return get_urls
admin.site.get_urls = custom_admin_urls(admin.site.get_urls())

from django.db.models import Sum
original_index = admin.site.index
def custom_index(self, request, extra_context=None):
    credit = FinanceTransaction.objects.filter(transaction_type="CREDIT").aggregate(Sum("amount"))["amount__sum"] or 0
    debit = FinanceTransaction.objects.filter(transaction_type="DEBIT").aggregate(Sum("amount"))["amount__sum"] or 0
    balance = credit - debit
    if extra_context is None:
        extra_context = {}
    extra_context["current_balance"] = balance
    extra_context['current_stock_url'] = reverse('admin:current-stock')
    return original_index(request, extra_context)
admin.site.index = custom_index.__get__(admin.site, AdminSite)
