from datetime import date
from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.test import TestCase

from .admin import EntryForm, InvoiceAdmin, InvoiceForm, InvoiceItemForm, QuotationForm
from .models import Contact, Entry, Finance, Invoice, InvoiceItem, Quotation, Stock


class InvoiceFinanceSyncTests(TestCase):
	def setUp(self):
		self.invoice_admin = InvoiceAdmin(Invoice, AdminSite())

	def _create_invoice(self, payment_status="PAID"):
		invoice = Invoice.objects.create(
			invoice_no="INV-2026-0001",
			date=date(2026, 4, 20),
			customer_name="Test Customer",
			mobile_num="9999999999",
			payment_status=payment_status,
		)
		InvoiceItem.objects.create(
			invoice=invoice,
			particulars="Laptop Service",
			quantity=1,
			price=Decimal("1000.00"),
			discount=Decimal("0.00"),
			gst=Decimal("0.00"),
		)
		invoice.save()
		return invoice

	def test_paid_invoice_creates_single_finance_entry(self):
		invoice = self._create_invoice(payment_status="PAID")

		self.invoice_admin._sync_invoice_finance_entry(invoice)

		finance_qs = Finance.objects.filter(description__startswith=f"Invoice {invoice.invoice_no}")
		self.assertEqual(finance_qs.count(), 1)
		finance = finance_qs.first()
		self.assertEqual(finance.transaction_type, "CREDIT")
		self.assertEqual(finance.amount, invoice.total_amount)

	def test_editing_paid_invoice_updates_existing_finance_without_duplication(self):
		invoice = self._create_invoice(payment_status="PAID")
		self.invoice_admin._sync_invoice_finance_entry(invoice)

		invoice.discount = Decimal("100.00")
		invoice.save()
		self.invoice_admin._sync_invoice_finance_entry(invoice)

		finance_qs = Finance.objects.filter(description__startswith=f"Invoice {invoice.invoice_no}")
		self.assertEqual(finance_qs.count(), 1)
		self.assertEqual(finance_qs.first().amount, invoice.total_amount)

	def test_sync_removes_existing_duplicate_finance_rows(self):
		invoice = self._create_invoice(payment_status="PAID")
		Finance.objects.create(
			date=invoice.date,
			transaction_type="CREDIT",
			amount=Decimal("1000.00"),
			reason="OTHER",
			description=f"Invoice {invoice.invoice_no} - {invoice.customer_name}",
		)
		Finance.objects.create(
			date=invoice.date,
			transaction_type="CREDIT",
			amount=Decimal("900.00"),
			reason="OTHER",
			description=f"Invoice {invoice.invoice_no} - {invoice.customer_name}",
		)

		self.invoice_admin._sync_invoice_finance_entry(invoice)

		finance_qs = Finance.objects.filter(description__startswith=f"Invoice {invoice.invoice_no}")
		self.assertEqual(finance_qs.count(), 1)
		self.assertEqual(finance_qs.first().amount, invoice.total_amount)

	def test_unpaid_invoice_removes_existing_finance_entry(self):
		invoice = self._create_invoice(payment_status="PAID")
		self.invoice_admin._sync_invoice_finance_entry(invoice)

		invoice.payment_status = "UNPAID"
		invoice.save()
		self.invoice_admin._sync_invoice_finance_entry(invoice)

		finance_qs = Finance.objects.filter(description__startswith=f"Invoice {invoice.invoice_no}")
		self.assertEqual(finance_qs.count(), 0)


class ContactBookTests(TestCase):
	def test_contact_created_automatically_from_new_entry(self):
		Entry.objects.create(
			date=date(2026, 4, 20),
			customer_name="Entry Customer",
			mobile_num="9000000001",
			product="Laptop",
			product_issue="No boot",
			product_with="Adapter",
			address="Entry Address",
			product_status="IN",
		)

		contact = Contact.objects.get(mobile_num="9000000001")
		self.assertEqual(contact.name, "Entry Customer")
		self.assertEqual(contact.address, "Entry Address")

	def test_contact_created_automatically_from_new_invoice(self):
		Invoice.objects.create(
			invoice_no="INV-2026-2001",
			date=date(2026, 4, 20),
			customer_name="Invoice Customer",
			mobile_num="9000000002",
			customer_address="Invoice Address",
		)

		contact = Contact.objects.get(mobile_num="9000000002")
		self.assertEqual(contact.name, "Invoice Customer")
		self.assertEqual(contact.address, "Invoice Address")

	def test_contact_created_automatically_from_new_quotation(self):
		Quotation.objects.create(
			date=date(2026, 4, 20),
			customer_name="Quotation Customer",
			mobile_num="9000000003",
			customer_address="Quotation Address",
		)

		contact = Contact.objects.get(mobile_num="9000000003")
		self.assertEqual(contact.name, "Quotation Customer")
		self.assertEqual(contact.address, "Quotation Address")

	def test_existing_contact_is_updated_not_duplicated_for_same_mobile(self):
		Contact.objects.create(name="Old Name", mobile_num="9000000004", address="Old Address")

		Entry.objects.create(
			date=date(2026, 4, 20),
			customer_name="New Name",
			mobile_num="9000000004",
			product="Desktop",
			product_issue="Slow",
			product_with="Mouse",
			address="New Address",
			product_status="IN",
		)

		self.assertEqual(Contact.objects.filter(mobile_num="9000000004").count(), 1)
		contact = Contact.objects.get(mobile_num="9000000004")
		self.assertEqual(contact.name, "New Name")
		self.assertEqual(contact.address, "New Address")


class ContactSelectionFormTests(TestCase):
	def setUp(self):
		self.contact = Contact.objects.create(
			name="Known Customer",
			mobile_num="9111111111",
			address="Known Address",
		)

	def test_entry_form_uses_selected_contact_details(self):
		form = EntryForm(
			data={
				"contact": str(self.contact.pk),
				"date": "2026-04-20",
				"customer_name": "Manual Name",
				"mobile_num": "9000000000",
				"product": "Monitor",
				"product_issue": "Blank screen",
				"product_with": "Power cable",
				"address": "Manual Address",
				"product_status": "IN",
			}
		)
		self.assertTrue(form.is_valid(), form.errors)
		self.assertEqual(form.cleaned_data["customer_name"], "Known Customer")
		self.assertEqual(form.cleaned_data["mobile_num"], "9111111111")
		self.assertEqual(form.cleaned_data["address"], "Known Address")

	def test_invoice_form_allows_manual_details_without_contact(self):
		form = InvoiceForm(
			data={
				"invoice_no": "INV-2026-3001",
				"date": "2026-04-20",
				"customer_name": "Manual Invoice Name",
				"mobile_num": "9222222222",
				"customer_address": "Manual Invoice Address",
				"discount": "0.00",
				"gst": "0.00",
				"advance_amount": "0.00",
				"notes": "",
				"payment_status": "UNPAID",
			}
		)
		self.assertTrue(form.is_valid(), form.errors)
		self.assertEqual(form.cleaned_data["customer_name"], "Manual Invoice Name")
		self.assertEqual(form.cleaned_data["mobile_num"], "9222222222")
		self.assertEqual(form.cleaned_data["customer_address"], "Manual Invoice Address")

	def test_quotation_form_uses_selected_contact_details(self):
		form = QuotationForm(
			data={
				"contact": str(self.contact.pk),
				"date": "2026-04-20",
				"customer_name": "Manual Quotation Name",
				"mobile_num": "9333333333",
				"customer_address": "Manual Quotation Address",
				"discount": "0.00",
				"gst": "0.00",
				"notes": "",
			}
		)
		self.assertTrue(form.is_valid(), form.errors)
		self.assertEqual(form.cleaned_data["customer_name"], "Known Customer")
		self.assertEqual(form.cleaned_data["mobile_num"], "9111111111")
		self.assertEqual(form.cleaned_data["customer_address"], "Known Address")


class InvoiceItemAutofillTests(TestCase):
	def setUp(self):
		self.contact = Contact.objects.create(
			name="Known Customer",
			mobile_num="9111111111",
			address="Known Address",
		)
		self.stock = Stock.objects.create(
			date=date(2026, 4, 20),
			product="Test Keyboard",
			quantity=10,
			sale_price=Decimal("1499.00"),
			cost_price=Decimal("1200.00"),
		)

	def test_stock_selection_autofills_particulars_and_price(self):
		form = InvoiceItemForm(
			data={
				"stock": str(self.stock.pk),
				"particulars": "",
				"quantity": 1,
				"price": "",
				"discount": "0.00",
				"gst": "0.00",
			}
		)
		self.assertTrue(form.is_valid(), form.errors)
		self.assertEqual(form.cleaned_data["particulars"], "Test Keyboard")
		self.assertEqual(form.cleaned_data["price"], Decimal("1499.00"))

	def test_manual_particulars_and_price_required_without_stock(self):
		form = InvoiceItemForm(
			data={
				"stock": "",
				"particulars": "",
				"quantity": 1,
				"price": "",
				"discount": "0.00",
				"gst": "0.00",
			}
		)
		self.assertFalse(form.is_valid())
		self.assertIn("particulars", form.errors)
		self.assertIn("price", form.errors)

	def test_invoice_form_contact_fills_required_blank_inputs(self):
		form = InvoiceForm(
			data={
				"contact": str(self.contact.pk),
				"invoice_no": "INV-2026-3002",
				"date": "2026-04-20",
				"customer_name": "",
				"mobile_num": "",
				"customer_address": "",
				"discount": "0.00",
				"gst": "0.00",
				"advance_amount": "0.00",
				"notes": "",
				"payment_status": "UNPAID",
			}
		)
		self.assertTrue(form.is_valid(), form.errors)
		self.assertEqual(form.cleaned_data["customer_name"], "Known Customer")
		self.assertEqual(form.cleaned_data["mobile_num"], "9111111111")
		self.assertEqual(form.cleaned_data["customer_address"], "Known Address")
