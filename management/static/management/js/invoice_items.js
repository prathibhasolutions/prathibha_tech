/* Auto-fill invoice item particulars and price from selected stock */
(function () {
	function getRowElement(selectEl) {
		if (!selectEl) {
			return null;
		}
		return selectEl.closest("tr.form-row") || selectEl.closest("tr");
	}

	function applyStockDetails(selectEl) {
		var row = getRowElement(selectEl);
		if (!row) {
			return;
		}

		var selectedOption = selectEl.options[selectEl.selectedIndex];
		if (!selectedOption) {
			return;
		}

		var product = selectedOption.getAttribute("data-stock-product") || "";
		var salePrice = selectedOption.getAttribute("data-sale-price") || "";

		var particularsInput = row.querySelector('input[name$="-particulars"]');
		var priceInput = row.querySelector('input[name$="-price"]');

		if (product && particularsInput) {
			particularsInput.value = product;
		}

		if (salePrice && priceInput) {
			var parsedPrice = parseFloat(salePrice);
			if (!Number.isNaN(parsedPrice)) {
				priceInput.value = parsedPrice.toFixed(2);
			} else {
				priceInput.value = salePrice;
			}
		}
	}

	function isStockSelect(element) {
		return !!(element && element.matches && element.matches('select[name$="-stock"]'));
	}

	function bindExistingRows() {
		var stockSelects = document.querySelectorAll('select[name$="-stock"]');
		stockSelects.forEach(function (selectEl) {
			if (selectEl.value) {
				applyStockDetails(selectEl);
			}
		});
	}

	document.addEventListener("change", function (event) {
		var target = event.target;
		if (isStockSelect(target)) {
			applyStockDetails(target);
		}
	});

	document.addEventListener("DOMContentLoaded", function () {
		bindExistingRows();
	});
})();
