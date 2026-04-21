from django.contrib import messages
from django.shortcuts import redirect, render

from .models import ServiceBooking


def home(request):
	if request.method == "POST":
		service_needed = request.POST.get("service_needed", "").strip()
		mobile_num = request.POST.get("mobile_num", "").strip()
		address = request.POST.get("address", "").strip()

		valid_services = {choice[0] for choice in ServiceBooking.SERVICE_CHOICES}
		if service_needed not in valid_services:
			messages.error(request, "Please select a valid service.")
		elif not mobile_num:
			messages.error(request, "Please enter mobile number.")
		elif not address:
			messages.error(request, "Please enter address.")
		else:
			ServiceBooking.objects.create(
				service_needed=service_needed,
				mobile_num=mobile_num,
				address=address,
			)
			messages.success(request, "Our technician will contact you soon.")

		return redirect("home")

	return render(request, "management/home.html", {"service_choices": ServiceBooking.SERVICE_CHOICES})
