document.addEventListener("DOMContentLoaded", function () {
    "use strict";

    // ============================================================
    // NEOLEARN MARKETPLACE
    //
    // JavaScript responsibilities:
    // ------------------------------------------------------------
    // 1. Open / close the filter drawer
    // 2. Handle overlay click
    // 3. Handle Escape key
    // 4. Lock / unlock page scrolling while drawer is open
    //
    // Django responsibilities:
    // ------------------------------------------------------------
    // 1. Search
    // 2. Batch filtering
    // 3. Status filtering
    // 4. Sorting
    // 5. Discount filtering
    // 6. Price filtering
    // 7. Add to cart
    // 8. Remove from cart
    // 9. Wishlist
    //
    // IMPORTANT:
    // No AJAX is used here.
    // No client-side validation is used here.
    // Django remains the source of truth.
    // ============================================================


    // ============================================================
    // ELEMENTS
    // ============================================================

    const filterToggle = document.getElementById("filterToggle");
    const filterPanel = document.getElementById("filterPanel");
    const filterDrawer = document.getElementById("filterDrawer");
    const filterOverlay = document.getElementById("filterOverlay");
    const filterClose = document.getElementById("filterClose");


    // ============================================================
    // SAFETY CHECK
    //
    // If the Marketplace filter drawer does not exist on the page,
    // do not execute any drawer-related code.
    // ============================================================

    if (
        !filterToggle ||
        !filterPanel ||
        !filterDrawer ||
        !filterOverlay ||
        !filterClose
    ) {
        return;
    }


    // ============================================================
    // DRAWER STATE
    // ============================================================

    let closeTimer = null;


    // ============================================================
    // OPEN FILTER DRAWER
    // ============================================================

    function openFilterDrawer() {

        // Cancel any pending close timer.
        if (closeTimer) {
            clearTimeout(closeTimer);
            closeTimer = null;
        }


        // Make overlay interactive.
        filterPanel.classList.remove(
            "pointer-events-none"
        );


        // Fade overlay in.
        filterPanel.classList.remove(
            "opacity-0"
        );

        filterPanel.classList.add(
            "opacity-100"
        );


        // Slide drawer into view.
        filterDrawer.classList.remove(
            "translate-x-full"
        );

        filterDrawer.classList.add(
            "translate-x-0"
        );


        // Accessibility state.
        filterPanel.setAttribute(
            "aria-hidden",
            "false"
        );


        // Prevent background page scrolling.
        document.body.classList.add(
            "overflow-hidden"
        );


        // Accessibility focus.
        if (typeof filterClose.focus === "function") {
            filterClose.focus();
        }
    }


    // ============================================================
    // CLOSE FILTER DRAWER
    // ============================================================

    function closeFilterDrawer() {

        // Slide drawer out.
        filterDrawer.classList.remove(
            "translate-x-0"
        );

        filterDrawer.classList.add(
            "translate-x-full"
        );


        // Fade overlay out.
        filterPanel.classList.remove(
            "opacity-100"
        );

        filterPanel.classList.add(
            "opacity-0"
        );


        // Accessibility state.
        filterPanel.setAttribute(
            "aria-hidden",
            "true"
        );


        // Restore page scrolling.
        document.body.classList.remove(
            "overflow-hidden"
        );


        // Wait for the transition before disabling pointer events.
        closeTimer = setTimeout(function () {

            if (
                filterPanel.getAttribute("aria-hidden") === "true"
            ) {
                filterPanel.classList.add(
                    "pointer-events-none"
                );
            }

            closeTimer = null;

        }, 300);
    }


    // ============================================================
    // FILTER TOGGLE BUTTON
    // ============================================================

    filterToggle.addEventListener(
        "click",
        function (event) {

            event.preventDefault();

            const isOpen =
                filterPanel.getAttribute("aria-hidden") === "false";

            if (isOpen) {
                closeFilterDrawer();
            } else {
                openFilterDrawer();
            }
        }
    );


    // ============================================================
    // CLOSE BUTTON
    // ============================================================

    filterClose.addEventListener(
        "click",
        function (event) {

            event.preventDefault();

            closeFilterDrawer();
        }
    );


    // ============================================================
    // OVERLAY CLICK
    // ============================================================

    filterOverlay.addEventListener(
        "click",
        function () {

            closeFilterDrawer();
        }
    );


    // ============================================================
    // ESCAPE KEY
    // ============================================================

    document.addEventListener(
        "keydown",
        function (event) {

            if (
                event.key === "Escape" &&
                filterPanel.getAttribute("aria-hidden") === "false"
            ) {
                closeFilterDrawer();
            }
        }
    );


    // ============================================================
    // INITIAL STATE
    //
    // Make sure the drawer is closed when the page loads.
    // ============================================================

    if (
        filterPanel.getAttribute("aria-hidden") !== "false"
    ) {

        filterPanel.setAttribute(
            "aria-hidden",
            "true"
        );

        filterPanel.classList.add(
            "opacity-0"
        );

        filterPanel.classList.add(
            "pointer-events-none"
        );

        filterDrawer.classList.add(
            "translate-x-full"
        );
    }


    // ============================================================
    // PAGE SCROLL CLEANUP
    //
    // Protect against the page remaining locked if navigation,
    // reload, or another browser event happens while the drawer
    // is open.
    // ============================================================

    window.addEventListener(
        "beforeunload",
        function () {

            document.body.classList.remove(
                "overflow-hidden"
            );
        }
    );


    // ============================================================
    // RESIZE SAFETY
    //
    // If the viewport changes while the drawer is open, keep the
    // drawer state controlled by the same CSS classes.
    // No filtering/navigation is performed here.
    // ============================================================

    window.addEventListener(
        "resize",
        function () {

            if (
                filterPanel.getAttribute("aria-hidden") === "true"
            ) {
                document.body.classList.remove(
                    "overflow-hidden"
                );
            }
        }
    );

});