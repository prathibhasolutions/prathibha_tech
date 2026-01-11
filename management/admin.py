
from django.contrib import admin
from django.urls import path, reverse
from django.template.response import TemplateResponse
from django.utils.html import format_html
from .models import Entry, Stock, Finance, Invoice, Quotation
from django.contrib import admin as django_admin

@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
	list_display = ("sl_no", "date", "customer_name", "mobile_num", "product_status")
	list_filter = ("product_status", "date")
	search_fields = ("customer_name", "mobile_num", "product_issue")

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
	list_display = ("sl_no", "date", "product", "serial_number", "quantity")
	list_filter = ("date",)
	search_fields = ("product", "serial_number")

@admin.register(Finance)
class FinanceAdmin(admin.ModelAdmin):
	list_display = ("sl_no", "date", "transaction_type", "amount", "reason")
	list_filter = ("transaction_type", "date")
	search_fields = ("reason", "description")
	
	def get_form(self, request, obj=None, **kwargs):
		from django import forms
		form = super().get_form(request, obj, **kwargs)
		
		class DynamicFinanceForm(form):
			def __init__(self, *args, **kwargs):
				super().__init__(*args, **kwargs)
				if self.instance and self.instance.transaction_type == "DEBIT":
					self.fields['reason'].widget = forms.Select(choices=Finance.DEBIT_REASON_CHOICES)
				else:
					self.fields['reason'].widget = forms.TextInput()
		
		return DynamicFinanceForm


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
	list_display = ("invoice_no", "date", "customer_name", "mobile_num", "total_amount", "balance", "print_link")
	list_filter = ("date",)
	search_fields = ("invoice_no", "customer_name", "mobile_num", "particulars")
	readonly_fields = ("total_amount", "balance")

	def print_link(self, obj):
		url = reverse("admin:management_invoice_print", args=[obj.pk])
		return format_html('<a class="button" href="{}" target="_blank">Print</a>', url)
	print_link.short_description = "Print"
	print_link.allow_tags = True

	def get_urls(self):
		urls = super().get_urls()
		custom = [
			path('<path:object_id>/print/', self.admin_site.admin_view(self.print_view), name='management_invoice_print'),
		]
		return custom + urls

	def print_view(self, request, object_id):
		obj = self.get_object(request, object_id)
		context = {
			**self.admin_site.each_context(request),
			"title": f"Invoice {obj.invoice_no}",
			"invoice": obj,
			"company": "Prathibha Technologies",
		}
		return TemplateResponse(request, "admin/invoice_print.html", context)


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
	list_display = ("sl_no", "date", "customer_name", "mobile_num", "total", "print_link")
	list_filter = ("date",)
	search_fields = ("sl_no", "customer_name", "mobile_num", "particulars")
	readonly_fields = ("total",)

	def print_link(self, obj):
		url = reverse("admin:management_quotation_print", args=[obj.pk])
		return format_html('<a class="button" href="{}" target="_blank">Print</a>', url)
	print_link.short_description = "Print"
	print_link.allow_tags = True

	def get_urls(self):
		urls = super().get_urls()
		custom = [
			path('<path:object_id>/print/', self.admin_site.admin_view(self.print_view), name='management_quotation_print'),
		]
		return custom + urls

	def print_view(self, request, object_id):
		obj = self.get_object(request, object_id)
		context = {
			**self.admin_site.each_context(request),
			"title": f"Quotation {obj.sl_no}",
			"quotation": obj,
			"company": "Prathibha Technologies",
		}
		return TemplateResponse(request, "admin/quotation_print.html", context)


# Customize admin branding
django_admin.site.site_header = "Prathibha Technologies"
django_admin.site.site_title = "Prathibha Technologies"
django_admin.site.index_title = "Prathibha Technologies"
