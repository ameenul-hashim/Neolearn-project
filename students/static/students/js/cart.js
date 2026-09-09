document.addEventListener("DOMContentLoaded", function () {
    "use strict";

    /*
     * =========================================================
     * NeoLearn Cart
     * =========================================================
     *
     * JavaScript is intentionally minimal.
     *
     * Django handles:
     * - cart data
     * - add/remove
     * - clear cart
     * - pricing
     * - coupon validation
     * - checkout amount
     *
     * JavaScript only handles:
     * - Clear Cart confirmation modal
     * - small coupon placeholder interaction
     *
     * The cart is always cleared by Django.
     */


    // =========================================================
    // CLEAR CART CONFIRMATION MODAL
    // =========================================================

    const clearCartForm = document.getElementById("clearCartForm");
    const clearCartButton = document.getElementById("clearCartButton");

    const clearCartModal = document.getElementById("clearCartModal");

    const cancelClearCartButton = document.getElementById(
        "cancelClearCartButton"
    );

    const confirmClearCartButton = document.getElementById(
        "confirmClearCartButton"
    );


    // =========================================================
    // OPEN CLEAR CART MODAL
    // =========================================================

    if (
        clearCartForm &&
        clearCartButton &&
        clearCartModal
    ) {
        clearCartButton.addEventListener("click", function (event) {

            /*
             * Prevent the original form submission.
             *
             * We want the user to confirm first.
             */

            event.preventDefault();

            clearCartModal.classList.remove("hidden");
            clearCartModal.classList.add("flex");

            /*
             * Prevent background page scrolling while
             * the confirmation modal is open.
             */

            document.body.classList.add("overflow-hidden");

            /*
             * Put keyboard focus on Cancel.
             */

            if (cancelClearCartButton) {
                cancelClearCartButton.focus();
            }
        });
    }


    // =========================================================
    // CLOSE CLEAR CART MODAL
    // =========================================================

    function closeClearCartModal() {

        if (!clearCartModal) {
            return;
        }

        clearCartModal.classList.add("hidden");
        clearCartModal.classList.remove("flex");

        document.body.classList.remove("overflow-hidden");
    }


    // =========================================================
    // CANCEL BUTTON
    // =========================================================

    if (cancelClearCartButton) {

        cancelClearCartButton.addEventListener(
            "click",
            function () {

                closeClearCartModal();
            }
        );
    }


    // =========================================================
    // CLICK OUTSIDE MODAL
    // =========================================================

    if (clearCartModal) {

        clearCartModal.addEventListener(
            "click",
            function (event) {

                /*
                 * Only close when the actual backdrop is clicked.
                 *
                 * Clicking inside the modal should do nothing.
                 */

                if (event.target === clearCartModal) {
                    closeClearCartModal();
                }
            }
        );
    }


    // =========================================================
    // CONFIRM CLEAR CART
    // =========================================================

    if (
        confirmClearCartButton &&
        clearCartForm
    ) {

        confirmClearCartButton.addEventListener(
            "click",
            function () {

                /*
                 * Prevent accidental double-click submission.
                 */

                confirmClearCartButton.disabled = true;

                confirmClearCartButton.classList.add(
                    "opacity-70",
                    "cursor-not-allowed"
                );


                /*
                 * IMPORTANT:
                 *
                 * JavaScript does NOT delete anything.
                 *
                 * It simply submits the existing Django form.
                 *
                 * Django handles:
                 * - cart lookup
                 * - deleting cart items
                 * - success/error messages
                 * - redirect
                 */

                clearCartForm.submit();
            }
        );
    }


    // =========================================================
    // ESC KEY
    // =========================================================

    document.addEventListener(
        "keydown",
        function (event) {

            if (
                event.key === "Escape" &&
                clearCartModal &&
                !clearCartModal.classList.contains("hidden")
            ) {
                closeClearCartModal();
            }
        }
    );


    // =========================================================
    // COUPON PLACEHOLDER
    //
    // Coupon backend will be connected after the Admin
    // Coupon Management system is implemented.
    // =========================================================

    const couponButton = document.getElementById(
        "couponApplyButton"
    );

    const couponInput = document.getElementById(
        "couponCode"
    );


    if (couponButton && couponInput) {

        couponButton.addEventListener(
            "click",
            function () {

                const couponCode = couponInput.value.trim();


                if (!couponCode) {

                    couponInput.focus();

                    return;
                }


                /*
                 * Do not validate the coupon in JavaScript.
                 *
                 * The real coupon validation will be handled
                 * by Django after the Admin Coupon system is
                 * connected.
                 */

                couponInput.setCustomValidity(
                    "Coupon system will be connected after Admin Coupon setup."
                );

                couponInput.reportValidity();

                couponInput.setCustomValidity("");
            }
        );
    }

});