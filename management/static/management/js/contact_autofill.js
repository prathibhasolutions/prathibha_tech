(function () {
  function applyContactToFields(selectEl) {
    if (!selectEl) {
      return;
    }

    var selectedOption = selectEl.options[selectEl.selectedIndex];
    if (!selectedOption) {
      return;
    }

    var nameInput = document.getElementById("id_customer_name");
    var mobileInput = document.getElementById("id_mobile_num");
    var addressInput = document.getElementById("id_customer_address") || document.getElementById("id_address");

    var contactName = selectedOption.getAttribute("data-contact-name") || "";
    var contactMobile = selectedOption.getAttribute("data-contact-mobile") || "";
    var contactAddress = selectedOption.getAttribute("data-contact-address") || "";

    if (!contactName && !contactMobile && !contactAddress) {
      return;
    }

    if (nameInput) {
      nameInput.value = contactName;
    }
    if (mobileInput) {
      mobileInput.value = contactMobile;
    }
    if (addressInput) {
      addressInput.value = contactAddress;
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var contactSelect = document.getElementById("id_contact");
    if (!contactSelect) {
      return;
    }

    contactSelect.addEventListener("change", function () {
      applyContactToFields(contactSelect);
    });
  });
})();
