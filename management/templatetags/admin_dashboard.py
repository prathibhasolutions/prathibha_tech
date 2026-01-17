from django import template
from management.models import Invoice

register = template.Library()

@register.simple_tag
def get_unpaid_invoices():
    return Invoice.objects.filter(payment_status="UNPAID").order_by("-date", "-invoice_no")