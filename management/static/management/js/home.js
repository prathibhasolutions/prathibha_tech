document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById("booking-modal");
    const successPopup = document.getElementById("success-popup");
    const closeSuccessButton = document.getElementById("close-success-popup");

    if (successPopup) {
        document.body.style.overflow = "hidden";

        const closeSuccessPopup = () => {
            successPopup.remove();
            document.body.style.overflow = "";
        };

        if (closeSuccessButton) {
            closeSuccessButton.addEventListener("click", closeSuccessPopup);
            closeSuccessButton.focus();
        }

        successPopup.addEventListener("click", (event) => {
            if (event.target === successPopup) {
                closeSuccessPopup();
            }
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closeSuccessPopup();
            }
        });
    }

    if (!modal) {
        return;
    }

    const closeBtn = document.getElementById("close-booking-modal");
    const openButtons = document.querySelectorAll(".js-book-service");

    const openModal = () => {
        modal.hidden = false;
        document.body.style.overflow = "hidden";
    };

    const closeModal = () => {
        modal.hidden = true;
        document.body.style.overflow = "";
    };

    openButtons.forEach((button) => {
        button.addEventListener("click", openModal);
    });

    if (closeBtn) {
        closeBtn.addEventListener("click", closeModal);
    }

    modal.addEventListener("click", (event) => {
        if (event.target === modal) {
            closeModal();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (!modal.hidden && event.key === "Escape") {
            closeModal();
        }
    });
});
