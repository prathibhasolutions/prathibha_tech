
from django.contrib import admin
from django.urls import path, reverse
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.db import models
from .models import Entry, Stock, Finance, Invoice, Quotation, InvoiceItem, QuotationItem
from django.contrib import admin as django_admin
from django import forms
from .utils import amount_to_words, generate_phonepe_qr

class EntryAdmin(admin.ModelAdmin):
	list_display = ("sl_no", "date", "customer_name", "mobile_num", "product_status")
	list_filter = ("product_status", "date")
	search_fields = ("customer_name", "mobile_num", "product_issue")

class StockAdmin(admin.ModelAdmin):
	list_display = ("sl_no", "date", "product","price", "serial_number", "quantity")
	list_filter = ("date",)
	search_fields = ("product", "serial_number")

class FinanceAdmin(admin.ModelAdmin):
	list_display = ("sl_no", "date", "transaction_type", "amount", "reason")
	list_filter = ("transaction_type", "date")
	search_fields = ("reason", "description")
	change_list_template = "admin/finance_changelist.html"

	def get_form(self, request, obj=None, **kwargs):
		from django import forms
		base_form = super().get_form(request, obj, **kwargs)

		class FinanceForm(base_form):
			def __init__(self, *args, **kwargs):
				super().__init__(*args, **kwargs)
				self.fields['reason'].widget = forms.Select(choices=Finance.REASON_CHOICES)

		return FinanceForm
	
	def changelist_view(self, request, extra_context=None):
		extra_context = extra_context or {}
		
		# Calculate totals
		credits = Finance.objects.filter(transaction_type="CREDIT").aggregate(total=models.Sum("amount"))["total"] or 0
		debits = Finance.objects.filter(transaction_type="DEBIT").aggregate(total=models.Sum("amount"))["total"] or 0
		balance = credits - debits
		
		extra_context["total_credits"] = f"₹{credits:,.2f}"
		extra_context["total_debits"] = f"₹{debits:,.2f}"
		extra_context["current_balance"] = f"₹{balance:,.2f}"
		
		return super().changelist_view(request, extra_context)


class InvoiceItemInline(admin.TabularInline):
	model = InvoiceItem
	extra = 1
	fields = ('particulars', 'quantity', 'price', 'discount', 'gst')
	verbose_name = "Particular"
	verbose_name_plural = "Particulars"


class InvoiceAdmin(admin.ModelAdmin):
	list_display = ("invoice_no", "date", "customer_name", "mobile_num", "total_amount", "balance", "payment_status", "print_link")
	list_filter = ("date", "payment_status")
	search_fields = ("invoice_no", "customer_name", "mobile_num")
	readonly_fields = ("invoice_no", "total_amount", "balance")
	inlines = [InvoiceItemInline]
	fieldsets = (
		("Invoice Details", {
			"fields": ("invoice_no", "date", "customer_name", "mobile_num", "customer_address")
		}),
		("Amounts", {
			"fields": ("discount", "gst", "advance_amount", "total_amount", "balance", "payment_status", "notes")
		}),
	)

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)
		# Recalculate totals after saving
		obj.save()

	def save_related(self, request, form, formsets, change):
		super().save_related(request, form, formsets, change)
		# Recalculate totals after saving related items
		form.instance.save()

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
		qr_code = generate_phonepe_qr(obj.total_amount)
		amount_words = amount_to_words(obj.total_amount)
		context = {
			**self.admin_site.each_context(request),
			"title": f"Invoice {obj.invoice_no}",
			"invoice": obj,
			"company": "Prathibha Computer & Hardware Services",
			"qr_code": qr_code,
			"amount_words": amount_words,
		}
		return TemplateResponse(request, "admin/invoice_print.html", context)



class QuotationItemInline(admin.TabularInline):
	model = QuotationItem
	extra = 1
	fields = ('particulars', 'quantity', 'price', 'discount', 'gst')
	verbose_name = "Particular"
	verbose_name_plural = "Particulars"


class QuotationAdmin(admin.ModelAdmin):
	list_display = ("sl_no", "date", "customer_name", "mobile_num", "total", "print_link")
	list_filter = ("date",)
	search_fields = ("sl_no", "customer_name", "mobile_num")
	readonly_fields = ("total",)
	inlines = [QuotationItemInline]
	fieldsets = (
		("Quotation Details", {
			"fields": ("date", "customer_name", "mobile_num", "customer_address")
		}),
		("Amounts", {
			"fields": ("discount", "gst", "total", "notes")
		}),
	)

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)
		# Recalculate totals after saving
		obj.save()

	def save_related(self, request, form, formsets, change):
		super().save_related(request, form, formsets, change)
		# Recalculate totals after saving related items
		form.instance.save()

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
		amount_words = amount_to_words(obj.total)
		context = {
			**self.admin_site.each_context(request),
			"title": f"Quotation {obj.sl_no}",
			"quotation": obj,
			"company": "Prathibha Computer & Hardware Services",
			"amount_words": amount_words,
		}
		return TemplateResponse(request, "admin/quotation_print.html", context)


# Customize admin branding and index view
class CustomAdminSite(admin.AdminSite):
	site_header = "Prathibha Computer & Hardware Services"
	site_title = "Prathibha Computer & Hardware Services"
	index_title = "Prathibha Computer & Hardware Services"
	
	def index(self, request, extra_context=None):
		extra_context = extra_context or {}
		# Get unpaid invoices for dashboard
		unpaid_invoices = Invoice.objects.filter(payment_status="UNPAID").order_by("-date", "-invoice_no")
		extra_context['unpaid_invoices'] = unpaid_invoices
		return super().index(request, extra_context)

# Replace default admin site
django_admin.site = CustomAdminSite(name='admin')

# Re-register all models with custom admin site
django_admin.site.register(Entry, EntryAdmin)
django_admin.site.register(Stock, StockAdmin)
django_admin.site.register(Finance, FinanceAdmin)
django_admin.site.register(Invoice, InvoiceAdmin)
django_admin.site.register(Quotation, QuotationAdmin)
