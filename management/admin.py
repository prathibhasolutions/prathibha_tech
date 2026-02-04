
from django.contrib import admin
from django.urls import path, reverse
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.db import models
from decimal import Decimal
from .models import Entry, Stock, Finance, Invoice, Quotation, InvoiceItem, QuotationItem, AuditEvent
from django.contrib import admin as django_admin
from django import forms
from .utils import amount_to_words, generate_phonepe_qr
from django.contrib.admin.models import ADDITION, CHANGE, DELETION
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator


class DateRangeFilter(admin.SimpleListFilter):
	"""From/To date range filter for DateField admin list views."""
	title = "Date range"
	parameter_name = "date_range"
	template = "admin/date_range_filter.html"

	def expected_parameters(self):
		return ["date__gte", "date__lte"]

	def lookups(self, request, model_admin):
		return ()

	def has_output(self):
		return True

	def queryset(self, request, queryset):
		date_from = self.used_parameters.get("date__gte")
		date_to = self.used_parameters.get("date__lte")
		if date_from:
			queryset = queryset.filter(date__gte=date_from)
		if date_to:
			queryset = queryset.filter(date__lte=date_to)
		return queryset


class AuditedModelAdmin(admin.ModelAdmin):
	"""ModelAdmin that mirrors admin log actions into immutable AuditEvent."""

	@staticmethod
	def _create_audit_event(request, obj, action, message=""):
		# Normalize change_message which can be a list/dict from admin log
		from json import dumps
		if isinstance(message, (list, dict)):
			try:
				message = dumps(message)
			except Exception:
				message = str(message)
		if message is None:
			message = ""

		AuditEvent.objects.create(
			user_id=request.user.id if getattr(request, "user", None) and request.user.is_authenticated else None,
			username=request.user.username if getattr(request, "user", None) and request.user.is_authenticated else None,
			action=action,
			content_type=ContentType.objects.get_for_model(obj) if obj else None,
			object_id=str(obj.pk) if obj and getattr(obj, "pk", None) is not None else None,
			object_repr=str(obj) if obj else None,
			message=message,
			ip_address=request.META.get("REMOTE_ADDR") if request else None,
		)

	def log_addition(self, request, obj, message):
		super().log_addition(request, obj, message)
		self._create_audit_event(request, obj, "ADD", message)

	def log_change(self, request, obj, message):
		super().log_change(request, obj, message)
		self._create_audit_event(request, obj, "CHANGE", message)

	def log_deletion(self, request, obj, object_repr):
		super().log_deletion(request, obj, object_repr)
		self._create_audit_event(request, obj, "DELETE", object_repr)

	def delete_model(self, request, obj):
		"""Capture audit before actual deletion."""
		obj_repr = str(obj)
		obj_pk = obj.pk
		obj_ct = ContentType.objects.get_for_model(obj)
		# Delete the object first
		super().delete_model(request, obj)
		# Now log to audit (obj is deleted but we saved the info)
		AuditEvent.objects.create(
			user_id=request.user.id if request.user.is_authenticated else None,
			username=request.user.username if request.user.is_authenticated else None,
			action="DELETE",
			content_type=obj_ct,
			object_id=str(obj_pk),
			object_repr=obj_repr,
			message=f"Deleted {obj_repr}",
			ip_address=request.META.get("REMOTE_ADDR"),
		)

	def delete_queryset(self, request, queryset):
		"""Capture audit for bulk deletions."""
		# Capture info before deletion
		objects_info = []
		for obj in queryset:
			objects_info.append({
				'pk': obj.pk,
				'repr': str(obj),
				'ct': ContentType.objects.get_for_model(obj)
			})
		# Delete the objects
		super().delete_queryset(request, queryset)
		# Log each deletion
		for info in objects_info:
			AuditEvent.objects.create(
				user_id=request.user.id if request.user.is_authenticated else None,
				username=request.user.username if request.user.is_authenticated else None,
				action="DELETE",
				content_type=info['ct'],
				object_id=str(info['pk']),
				object_repr=info['repr'],
				message=f"Deleted {info['repr']}",
				ip_address=request.META.get("REMOTE_ADDR"),
			)


class InvoiceItemForm(forms.ModelForm):
	"""Form for InvoiceItem with stock selection and available qty display"""
	
	class Meta:
		model = InvoiceItem
		fields = ('stock', 'particulars', 'quantity', 'price', 'discount', 'gst')
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		
		# Build stock choices with available quantity info
		stock_choices = [('', '-- Select Stock --')]
		stock_items = Stock.objects.all().order_by('product')
		
		for stock in stock_items:
			label = f"{stock.product} (Available: {stock.quantity})"
			stock_choices.append((stock.sl_no, label))
		
		self.fields['stock'].widget = forms.Select(choices=stock_choices)
		self.fields['stock'].required = False
		self.fields['stock'].label = "Particulars"
		
		# Pre-fill particulars from stock if available
		if self.instance.pk and self.instance.stock:
			self.fields['particulars'].initial = self.instance.stock.product
	
	def clean(self):
		cleaned_data = super().clean()
		stock = cleaned_data.get('stock')
		
		if stock:
			# Auto-fill particulars and price from stock
			cleaned_data['particulars'] = stock.product
			# Only set price from stock if user did not enter one
			entered_price = cleaned_data.get('price')
			if entered_price in (None, ""):
				cleaned_data['price'] = stock.price or Decimal("0.00")
		
		return cleaned_data


class EntryAdmin(AuditedModelAdmin):
	list_display = ("sl_no", "date", "customer_name", "mobile_num", "product_status")
	list_filter = ("product_status", "date")
	search_fields = ("customer_name", "mobile_num", "product_issue")

class StockAdmin(AuditedModelAdmin):
	list_display = ("sl_no", "date", "product","price", "serial_number", "quantity")
	list_filter = ("date",)
	search_fields = ("product", "serial_number")

class FinanceAdmin(AuditedModelAdmin):
	list_display = ("sl_no", "date", "transaction_type", "amount", "reason")
	list_filter = ("transaction_type", DateRangeFilter)
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
		
		date_from = request.GET.get("date__gte")
		date_to = request.GET.get("date__lte")
		base_qs = Finance.objects.all()
		if date_from:
			base_qs = base_qs.filter(date__gte=date_from)
		if date_to:
			base_qs = base_qs.filter(date__lte=date_to)
		
		# Calculate totals (respect date range filter)
		credits = base_qs.filter(transaction_type="CREDIT").aggregate(total=models.Sum("amount"))["total"] or 0
		debits = base_qs.filter(transaction_type="DEBIT").aggregate(total=models.Sum("amount"))["total"] or 0
		balance = credits - debits
		
		extra_context["total_credits"] = f"₹{credits:,.2f}"
		extra_context["total_debits"] = f"₹{debits:,.2f}"
		extra_context["current_balance"] = f"₹{balance:,.2f}"
		
		return super().changelist_view(request, extra_context)


class InvoiceItemInline(admin.TabularInline):
	model = InvoiceItem
	form = InvoiceItemForm
	extra = 1
	fields = ('stock', 'particulars', 'quantity', 'price', 'discount', 'gst')
	verbose_name = "Particular"
	verbose_name_plural = "Particulars"


class InvoiceAdmin(AuditedModelAdmin):
	list_display = ("invoice_no", "date", "customer_name", "mobile_num", "total_amount", "balance", "payment_status", "print_link")
	list_filter = (DateRangeFilter, "payment_status")
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
		
		# Create Finance entry if invoice is PAID (on creation or status change)
		invoice = form.instance
		if invoice.payment_status == "PAID" and invoice.total_amount > 0:
			# Check if Finance entry already exists for this invoice
			from datetime import datetime
			
			if not Finance.objects.filter(
				transaction_type="CREDIT",
				amount=invoice.total_amount,
				description__contains=f"Invoice {invoice.invoice_no}"
			).exists():
				Finance.objects.create(
					date=datetime.now().date(),
					transaction_type="CREDIT",
					amount=invoice.total_amount,
					reason="OTHER",
					description=f"Invoice {invoice.invoice_no} - {invoice.customer_name}"
				)

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


class QuotationAdmin(AuditedModelAdmin):
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
	
	def log_action(self, user_id, content_type_id, object_id, object_repr, action_flag, change_message=None):
		"""Log to default LogEntry plus immutable AuditEvent."""
		super().log_action(user_id, content_type_id, object_id, object_repr, action_flag, change_message)
		action_map = {
			ADDITION: "ADD",
			CHANGE: "CHANGE",
			DELETION: "DELETE",
		}
		AuditEvent.objects.create(
			user_id=user_id,
			username=self._user_username(user_id),
			action=action_map.get(action_flag, "OTHER"),
			content_type_id=content_type_id,
			object_id=object_id,
			object_repr=object_repr,
			message=change_message or "",
		)

	@staticmethod
	def _user_username(user_id):
		from django.contrib.auth import get_user_model
		User = get_user_model()
		try:
			return User.objects.get(pk=user_id).username
		except User.DoesNotExist:
			return None

	def get_urls(self):
		urls = super().get_urls()
		custom = [
			path('history/', self.admin_view(self.history_view), name='audit_history'),
		]
		return custom + urls

	def history_view(self, request):
		events = AuditEvent.objects.all().order_by('-created_at')
		paginator = Paginator(events, 50)
		page_number = request.GET.get('page') or 1
		page_obj = paginator.get_page(page_number)
		context = {
			**self.each_context(request),
			"title": "History",
			"events": page_obj.object_list,
			"page_obj": page_obj,
			"paginator": paginator,
			"is_paginated": page_obj.has_other_pages(),
		}
		return TemplateResponse(request, "admin/history.html", context)

	def index(self, request, extra_context=None):
		extra_context = extra_context or {}
		# Get unpaid invoices for dashboard
		unpaid_invoices = Invoice.objects.filter(payment_status="UNPAID").order_by("-date", "-invoice_no")
		extra_context['unpaid_invoices'] = unpaid_invoices
		# Stocks that need refilling
		extra_context['zero_stock_items'] = Stock.objects.filter(quantity__lte=0).order_by('product')
		extra_context['history_url'] = reverse('admin:audit_history')
		return super().index(request, extra_context)

# Replace default admin site
django_admin.site = CustomAdminSite(name='admin')

# Re-register all models with custom admin site
django_admin.site.register(Entry, EntryAdmin)
django_admin.site.register(Stock, StockAdmin)
django_admin.site.register(Finance, FinanceAdmin)
django_admin.site.register(Invoice, InvoiceAdmin)
django_admin.site.register(Quotation, QuotationAdmin)


class AuditEventAdmin(admin.ModelAdmin):
	list_display = ("created_at", "action", "username", "content_type", "object_repr")
	list_filter = ("action", "content_type")
	search_fields = ("username", "object_repr", "message")
	readonly_fields = (
		"created_at",
		"user_id",
		"username",
		"action",
		"content_type",
		"object_id",
		"object_repr",
		"message",
		"ip_address",
	)
	ordering = ("-created_at",)
	actions = None

	def has_add_permission(self, request):
		return False

	def has_delete_permission(self, request, obj=None):
		return False

	def has_change_permission(self, request, obj=None):
		# View-only; change disabled
		return False

	def has_view_permission(self, request, obj=None):
		return request.user.is_active and request.user.is_staff

	def has_module_permission(self, request):
		# Hide from sidebar; accessible via custom History view link
		return False


# Register audit events as read-only
django_admin.site.register(AuditEvent, AuditEventAdmin)


# ---------------------------------------------------------------------------
# AUTH SIGNALS (login/logout) -> AuditEvent
# ---------------------------------------------------------------------------


def _auth_event_handler(action):
	def handler(sender, request, user, **kwargs):
		ip = request.META.get("REMOTE_ADDR") if request else None
		AuditEvent.objects.create(
			user_id=user.id if user else None,
			username=getattr(user, "username", None),
			action=action,
			message=f"User {action.lower()} event",
			ip_address=ip,
		)
	return handler


user_logged_in.connect(_auth_event_handler("LOGIN"))
user_logged_out.connect(_auth_event_handler("LOGOUT"))
