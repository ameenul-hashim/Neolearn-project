document.addEventListener("DOMContentLoaded", function () {
    // ============================================================
    // CLEAR CART MODAL
    // ============================================================

    const clearCartButton = document.getElementById("clearCartButton");
    const clearCartModal = document.getElementById("clearCartModal");
    const cancelClearCartButton = document.getElementById(
        "cancelClearCartButton"
    );
    const confirmClearCartButton = document.getElementById(
        "confirmClearCartButton"
    );
    const clearCartForm = document.getElementById("clearCartForm");

    function openClearCartModal() {
        if (!clearCartModal) {
            return;
        }

        clearCartModal.classList.remove("hidden");
        clearCartModal.classList.add("flex");

        document.body.classList.add("overflow-hidden");

        if (cancelClearCartButton) {
            cancelClearCartButton.focus();
        }
    }

    function closeClearCartModal() {
        if (!clearCartModal) {
            return;
        }

        clearCartModal.classList.add("hidden");
        clearCartModal.classList.remove("flex");

        document.body.classList.remove("overflow-hidden");
    }


    // ============================================================
    // OPEN CLEAR CART MODAL
    // ============================================================

    if (clearCartButton) {
        clearCartButton.addEventListener("click", function (event) {
            event.preventDefault();

            openClearCartModal();
        });
    }


    // ============================================================
    // CANCEL CLEAR CART
    // ============================================================

    if (cancelClearCartButton) {
        cancelClearCartButton.addEventListener("click", function (event) {
            event.preventDefault();

            closeClearCartModal();
        });
    }


    // ============================================================
    // CONFIRM CLEAR CART
    // ============================================================

    if (confirmClearCartButton && clearCartForm) {
        confirmClearCartButton.addEventListener(
            "click",
            function (event) {
                event.preventDefault();

                confirmClearCartButton.disabled = true;

                confirmClearCartButton.classList.add(
                    "opacity-60",
                    "cursor-not-allowed"
                );

                clearCartForm.submit();
            }
        );
    }


    // ============================================================
    // CLOSE MODAL WHEN CLICKING BACKDROP
    // ============================================================

    if (clearCartModal) {
        clearCartModal.addEventListener("click", function (event) {
            if (event.target === clearCartModal) {
                closeClearCartModal();
            }
        });
    }


    // ============================================================
    // CLOSE MODAL WITH ESCAPE
    // ============================================================

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closeClearCartModal();
        }
    });


    // ============================================================
    // COUPON
    // ============================================================
    //
    // Coupon validation, eligibility checks, discount calculation,
    // usage limits, and cart totals are handled completely by Django.
    //
    // JavaScript does NOT:
    // - validate coupon codes
    // - calculate discounts
    // - calculate cart totals
    // - check coupon eligibility
    // - check minimum purchase
    // - check usage limits
    //
    // All coupon rules remain server-side.
    // ============================================================


    // ============================================================
    // PREVENT DOUBLE SUBMISSION
    // FOR MANUAL COUPON CODE
    // ============================================================

    const couponForm = document.getElementById("couponApplyForm");
    const couponApplyButton = document.getElementById(
        "couponApplyButton"
    );

    if (couponForm && couponApplyButton) {
        couponForm.addEventListener("submit", function () {
            couponApplyButton.disabled = true;

            couponApplyButton.classList.add(
                "opacity-60",
                "cursor-not-allowed"
            );

            couponApplyButton.innerHTML = `
                <svg
                    class="h-5 w-5 animate-spin"
                    viewBox="0 0 24 24"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                    aria-hidden="true"
                >
                    <circle
                        class="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        stroke-width="4"
                    ></circle>

                    <path
                        class="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                    ></path>
                </svg>

                <span>Applying...</span>
            `;
        });
    }
});