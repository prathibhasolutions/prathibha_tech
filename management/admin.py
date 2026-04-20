
from django.contrib import admin
from django.urls import path, reverse
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.db import models
from decimal import Decimal
from .models import Entry, Stock, Finance, Contact, Invoice, Quotation, InvoiceItem, QuotationItem, AuditEvent
from django.contrib import admin as django_admin
from django import forms
from .utils import amount_to_words, generate_phonepe_qr
from django.contrib.admin.models import ADDITION, CHANGE, DELETION
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date


class DateRangeFilter(admin.SimpleListFilter):
	"""From/To date range filter for DateField admin list views."""
	title = "Date range"
	parameter_name = "date_range"
	template = "admin/date_range_filter.html"

	def __init__(self, request, params, model, model_admin):
		super().__init__(request, params, model, model_admin)
		# Pop date params from lookup_params so Django doesn't treat them as
		# raw ORM filters (empty strings cause a ValueError -> ?e=1 redirect).
		self.used_parameters['date__gte'] = params.pop('date__gte', None)
		self.used_parameters['date__lte'] = params.pop('date__lte', None)

	def expected_parameters(self):
		return ["date__gte", "date__lte"]

	def lookups(self, request, model_admin):
		return ()

	def has_output(self):
		# Always show the filter UI
		return True

	def queryset(self, request, queryset):
		# Normalize values coming from GET (can be list/tuple/empty string).
		date_from = self.used_parameters.get("date__gte")
		date_to = self.used_parameters.get("date__lte")

		if isinstance(date_from, (list, tuple)):
			date_from = date_from[0] if date_from else None
		if isinstance(date_to, (list, tuple)):
			date_to = date_to[0] if date_to else None

		if date_from == "":
			date_from = None
		if date_to == "":
			date_to = None

		# Guard against malformed values (prevents admin from redirecting to ?e=1).
		if date_from and (not isinstance(date_from, str) or parse_date(date_from) is None):
			date_from = None
		if date_to and (not isinstance(date_to, str) or parse_date(date_to) is None):
			date_to = None

		if not date_from:
			self.used_parameters.pop("date__gte", None)
		if not date_to:
			self.used_parameters.pop("date__lte", None)
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

	class StockSelect(forms.Select):
		"""Select widget with stock metadata for client-side autofill."""

		def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
			option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
			stock = getattr(value, "instance", None)
			if stock is not None:
				option["attrs"].update(
					{
						"data-stock-product": stock.product or "",
						"data-sale-price": str(stock.sale_price or Decimal("0.00")),
					}
				)
			return option

	class StockChoiceField(forms.ModelChoiceField):
		def label_from_instance(self, obj):
			return f"{obj.product} (Available: {obj.quantity})"

	stock = StockChoiceField(
		queryset=Stock.objects.none(),
		required=False,
		widget=StockSelect,
	)
	
	class Meta:
		model = InvoiceItem
		fields = ('stock', 'particulars', 'quantity', 'price', 'discount', 'gst')
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.fields['stock'].queryset = Stock.objects.all().order_by('product')
		self.fields['stock'].widget.attrs.update({
			"style": "width: 100%; max-width: 280px;",
		})
		self.fields['stock'].required = False
		self.fields['stock'].label = "Particulars"
		self.fields['particulars'].required = False
		self.fields['price'].required = False
		
		# Pre-fill particulars from stock if available
		if self.instance.pk and self.instance.stock:
			self.fields['particulars'].initial = self.instance.stock.product
	
	def clean(self):
		cleaned_data = super().clean()
		stock = cleaned_data.get('stock')
		entered_price = cleaned_data.get('price')
		entered_particulars = cleaned_data.get('particulars')
		
		if stock:
			# Auto-fill particulars and price from stock
			cleaned_data['particulars'] = stock.product
			# Only set price from stock if user did not enter one
			if entered_price in (None, ""):
				cleaned_data['price'] = stock.sale_price or Decimal("0.00")
		else:
			if not entered_particulars:
				self.add_error('particulars', 'This field is required.')
			if entered_price in (None, ""):
				self.add_error('price', 'This field is required.')
		
		return cleaned_data


class ContactSelect(forms.Select):
	"""Select widget that embeds contact details for client-side autofill."""

	def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
		option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
		contact = getattr(value, "instance", None)
		if contact is not None:
			option["attrs"].update(
				{
					"data-contact-name": contact.name or "",
					"data-contact-mobile": contact.mobile_num or "",
					"data-contact-address": contact.address or "",
				}
			)
		return option


def _apply_bound_contact_data(form, address_field_name):
	"""Populate bound form data from selected contact before validation runs."""
	if not form.is_bound:
		return

	contact_id = form.data.get("contact")
	if not contact_id:
		return

	try:
		contact = Contact.objects.get(pk=contact_id)
	except (Contact.DoesNotExist, ValueError, TypeError):
		return

	bound_data = form.data.copy()
	bound_data["customer_name"] = contact.name or ""
	bound_data["mobile_num"] = contact.mobile_num or ""
	bound_data[address_field_name] = contact.address or ""
	form.data = bound_data


class EntryForm(forms.ModelForm):
	contact = forms.ModelChoiceField(
		queryset=Contact.objects.none(),
		required=False,
		widget=ContactSelect,
		help_text="Select an existing contact to auto-fill customer details.",
	)

	class Meta:
		model = Entry
		fields = "__all__"

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		_apply_bound_contact_data(self, "address")
		self.fields["contact"].queryset = Contact.objects.all().order_by("name", "mobile_num")
		if self.instance.pk and self.instance.mobile_num:
			self.fields["contact"].initial = Contact.objects.filter(mobile_num=self.instance.mobile_num).first()

	def clean(self):
		cleaned_data = super().clean()
		contact = cleaned_data.get("contact")
		if contact:
			cleaned_data["customer_name"] = contact.name
			cleaned_data["mobile_num"] = contact.mobile_num
			cleaned_data["address"] = contact.address
		return cleaned_data


class InvoiceForm(forms.ModelForm):
	contact = forms.ModelChoiceField(
		queryset=Contact.objects.none(),
		required=False,
		widget=ContactSelect,
		help_text="Select an existing contact to auto-fill customer details.",
	)

	class Meta:
		model = Invoice
		fields = "__all__"

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		_apply_bound_contact_data(self, "customer_address")
		self.fields["contact"].queryset = Contact.objects.all().order_by("name", "mobile_num")
		if self.instance.pk and self.instance.mobile_num:
			self.fields["contact"].initial = Contact.objects.filter(mobile_num=self.instance.mobile_num).first()

	def clean(self):
		cleaned_data = super().clean()
		contact = cleaned_data.get("contact")
		if contact:
			cleaned_data["customer_name"] = contact.name
			cleaned_data["mobile_num"] = contact.mobile_num
			cleaned_data["customer_address"] = contact.address
		return cleaned_data


class QuotationForm(forms.ModelForm):
	contact = forms.ModelChoiceField(
		queryset=Contact.objects.none(),
		required=False,
		widget=ContactSelect,
		help_text="Select an existing contact to auto-fill customer details.",
	)

	class Meta:
		model = Quotation
		fields = "__all__"

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		_apply_bound_contact_data(self, "customer_address")
		self.fields["contact"].queryset = Contact.objects.all().order_by("name", "mobile_num")
		if self.instance.pk and self.instance.mobile_num:
			self.fields["contact"].initial = Contact.objects.filter(mobile_num=self.instance.mobile_num).first()

	def clean(self):
		cleaned_data = super().clean()
		contact = cleaned_data.get("contact")
		if contact:
			cleaned_data["customer_name"] = contact.name
			cleaned_data["mobile_num"] = contact.mobile_num
			cleaned_data["customer_address"] = contact.address
		return cleaned_data


class EntryAdmin(AuditedModelAdmin):
	form = EntryForm
	list_display = ("sl_no", "date", "customer_name", "mobile_num", "product_status")
	list_filter = ("product_status", DateRangeFilter)
	search_fields = ("customer_name", "mobile_num", "product_issue")
	fieldsets = (
		("Customer", {
			"fields": ("contact", "customer_name", "mobile_num", "address")
		}),
		("Entry Details", {
			"fields": ("date", "product", "product_issue", "product_with", "product_status")
		}),
	)

	class Media:
		js = ("management/js/contact_autofill.js", "management/js/invoice_items.js")



class StockAdmin(AuditedModelAdmin):
	list_display = ("sl_no", "date", "product", "sale_price", "serial_number", "quantity")
	list_filter = (DateRangeFilter,)
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

		debit_reason_map = [
			("SHOP_MAINTENANCE", "Shop maintenance"),
			("LOCAL_SERVICE", "Local service"),
			("BY_ORDER_FROM_DEALER", "By order from dealer"),
			("STOCK_FROM_LOCAL", "Stock from local"),
		]
		debit_reason_totals = []
		for reason_key, reason_label in debit_reason_map:
			reason_total = base_qs.filter(transaction_type="DEBIT", reason=reason_key).aggregate(total=models.Sum("amount"))["total"] or 0
			debit_reason_totals.append(
				{
					"key": reason_key,
					"label": reason_label,
					"amount": f"₹{reason_total:,.2f}",
				}
			)
		
		extra_context["total_credits"] = f"₹{credits:,.2f}"
		extra_context["total_debits"] = f"₹{debits:,.2f}"
		extra_context["current_balance"] = f"₹{balance:,.2f}"
		extra_context["debit_reason_totals"] = debit_reason_totals
		
		return super().changelist_view(request, extra_context)


class ContactAdmin(AuditedModelAdmin):
	list_display = ("name", "mobile_num", "address")
	search_fields = ("name", "mobile_num", "address")


class InvoiceItemInline(admin.TabularInline):
	model = InvoiceItem
	form = InvoiceItemForm
	extra = 1
	fields = ('stock', 'particulars', 'quantity', 'price', 'discount', 'gst')
	verbose_name = "Particular"
	verbose_name_plural = "Particulars"


class InvoiceAdmin(AuditedModelAdmin):
	form = InvoiceForm
	list_display = ("invoice_no", "date", "customer_name", "mobile_num", "total_amount", "balance", "payment_status", "print_link")
	list_filter = (DateRangeFilter, "payment_status")
	search_fields = ("invoice_no", "customer_name", "mobile_num")
	readonly_fields = ("invoice_no", "total_amount", "balance")
	inlines = [InvoiceItemInline]
	fieldsets = (
		("Invoice Details", {
			"fields": ("contact", "invoice_no", "date", "customer_name", "mobile_num", "customer_address")
		}),
		("Amounts", {
			"fields": ("discount", "gst", "advance_amount", "total_amount", "balance", "payment_status", "notes")
		}),
	)

	class Media:
		js = ("management/js/contact_autofill.js",)



	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)
		# Recalculate totals after saving
		obj.save()

	def _sync_invoice_finance_entry(self, invoice):
		"""Keep exactly one finance credit entry per invoice when it is payable."""
		invoice_prefix = f"Invoice {invoice.invoice_no}"
		existing_qs = Finance.objects.filter(
			transaction_type="CREDIT",
			description__startswith=invoice_prefix,
		).order_by("sl_no")

		if invoice.payment_status == "PAID" and invoice.total_amount > 0:
			primary_entry = existing_qs.first()
			if primary_entry:
				primary_entry.date = invoice.date
				primary_entry.amount = invoice.total_amount
				primary_entry.reason = "OTHER"
				primary_entry.description = f"Invoice {invoice.invoice_no} - {invoice.customer_name}"
				primary_entry.save(update_fields=["date", "amount", "reason", "description"])
				# Remove any previously duplicated rows for the same invoice.
				existing_qs.exclude(pk=primary_entry.pk).delete()
			else:
				Finance.objects.create(
					date=invoice.date,
					transaction_type="CREDIT",
					amount=invoice.total_amount,
					reason="OTHER",
					description=f"Invoice {invoice.invoice_no} - {invoice.customer_name}",
				)
		else:
			existing_qs.delete()

	def save_related(self, request, form, formsets, change):
		super().save_related(request, form, formsets, change)
		# Recalculate totals after saving related items
		form.instance.save()

		self._sync_invoice_finance_entry(form.instance)

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
		# Calculate total due after subtracting advance
		total_due = obj.total_amount - (obj.advance_amount or 0)
		qr_code = generate_phonepe_qr(total_due)
		amount_words = amount_to_words(total_due)
		context = {
			**self.admin_site.each_context(request),
			"title": f"Invoice {obj.invoice_no}",
			"invoice": obj,
			   "company": "Prathibha Computers & Hardware Services",
			"qr_code": qr_code,
			"amount_words": amount_words,
			"total_due": total_due,
		}
		return TemplateResponse(request, "admin/invoice_print.html", context)



class QuotationItemInline(admin.TabularInline):
	model = QuotationItem
	extra = 1
	fields = ('particulars', 'quantity', 'price', 'discount', 'gst')
	verbose_name = "Particular"
	verbose_name_plural = "Particulars"



class QuotationAdmin(AuditedModelAdmin):
	form = QuotationForm

	actions = ["duplicate_quotation"]

	def duplicate_quotation(self, request, queryset):
		for quotation in queryset:
			# Duplicate the quotation
			quotation_fields = {
				field.name: getattr(quotation, field.name)
				for field in quotation._meta.fields
				if field.name not in ["id", "sl_no"]
			}
			new_quotation = Quotation.objects.create(**quotation_fields)
			# Duplicate related items
			for item in quotation.items.all():
				item_fields = {
					field.name: getattr(item, field.name)
					for field in item._meta.fields
					if field.name not in ["id", "quotation"]
				}
				QuotationItem.objects.create(quotation=new_quotation, **item_fields)
			# Now calculate subtotal from new_quotation's items
			subtotal = sum([
				item.quantity * item.price for item in new_quotation.items.all()
			])
			new_quotation.total = subtotal
			new_quotation.save()
		self.message_user(request, "Selected quotations duplicated successfully.")
	duplicate_quotation.short_description = "Duplicate selected quotations"

	list_display = ("sl_no", "date", "customer_name", "mobile_num", "total", "print_link")
	list_filter = (DateRangeFilter,)
	search_fields = ("sl_no", "customer_name", "mobile_num")
	readonly_fields = ("total",)
	inlines = [QuotationItemInline]


	fieldsets = (
		("Quotation Details", {
			"fields": ("contact", "date", "customer_name", "mobile_num", "customer_address")
		}),
		("Amounts", {
			"fields": ("discount", "gst", "total", "notes")
		}),
	)

	class Media:
		js = ("management/js/contact_autofill.js",)

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


	# ...existing code...

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
			message=change_message,
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
		# Calculate total due amount
		total_due = sum(inv.balance for inv in unpaid_invoices)
		extra_context['total_due_unpaid_invoices'] = total_due
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
django_admin.site.register(Contact, ContactAdmin)
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
