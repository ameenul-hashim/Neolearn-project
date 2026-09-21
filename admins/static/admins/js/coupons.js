document.addEventListener("DOMContentLoaded", () => {
    const filterButton = document.getElementById("couponFilterButton");
    const filterPanel = document.getElementById("couponFilterPanel");
    const filterChevron = document.getElementById("couponFilterChevron");

    const deleteModal = document.getElementById("deleteCouponModal");
    const deleteCode = document.getElementById("deleteCouponCode");
    const deleteForm = document.getElementById("deleteCouponConfirmForm");
    const cancelDelete = document.getElementById("cancelDeleteCoupon");

    const menuButtons = document.querySelectorAll(".couponMenuButton");
    const copyButtons = document.querySelectorAll(".copyCouponButton");
    const deleteButtons = document.querySelectorAll(".deleteCouponButton");


    /* ==========================================================
       FILTER PANEL
    ========================================================== */

    function closeFilterPanel() {
        if (!filterPanel || !filterButton) {
            return;
        }

        filterPanel.classList.add("hidden");
        filterButton.setAttribute(
            "aria-expanded",
            "false"
        );

        if (filterChevron) {
            filterChevron.classList.remove(
                "rotate-180"
            );
        }
    }


    function openFilterPanel() {
        if (!filterPanel || !filterButton) {
            return;
        }

        filterPanel.classList.remove("hidden");

        filterButton.setAttribute(
            "aria-expanded",
            "true"
        );

        if (filterChevron) {
            filterChevron.classList.add(
                "rotate-180"
            );
        }
    }


    filterButton?.addEventListener(
        "click",
        (event) => {
            event.stopPropagation();

            const isOpen =
                filterButton.getAttribute(
                    "aria-expanded"
                ) === "true";

            if (isOpen) {
                closeFilterPanel();
            } else {
                closeAllMenus();
                openFilterPanel();
            }
        }
    );


    /* ==========================================================
       ACTION MENUS
    ========================================================== */

    function closeAllMenus(except = null) {
        menuButtons.forEach((button) => {
            const menuId =
                button.getAttribute(
                    "aria-controls"
                );

            const menu = menuId
                ? document.getElementById(menuId)
                : null;

            if (!menu || menu === except) {
                return;
            }

            menu.classList.add("hidden");

            button.setAttribute(
                "aria-expanded",
                "false"
            );
        });
    }


    menuButtons.forEach((button) => {
        button.addEventListener(
            "click",
            (event) => {
                event.stopPropagation();

                const menuId =
                    button.getAttribute(
                        "aria-controls"
                    );

                const menu = menuId
                    ? document.getElementById(menuId)
                    : null;

                if (!menu) {
                    return;
                }

                const isOpen =
                    !menu.classList.contains(
                        "hidden"
                    );

                closeAllMenus();

                if (!isOpen) {
                    closeFilterPanel();

                    menu.classList.remove(
                        "hidden"
                    );

                    button.setAttribute(
                        "aria-expanded",
                        "true"
                    );
                }
            }
        );
    });


    /* ==========================================================
       COPY COUPON CODE
    ========================================================== */

    copyButtons.forEach((button) => {
        button.addEventListener(
            "click",
            async () => {
                const code =
                    button.dataset.code || "";

                if (!code) {
                    return;
                }

                try {
                    await navigator.clipboard.writeText(
                        code
                    );

                    const icon =
                        button.querySelector("i");

                    if (icon) {
                        icon.className =
                            "ri-check-line text-sm";
                    }

                    button.setAttribute(
                        "title",
                        "Copied"
                    );

                    window.setTimeout(() => {
                        if (icon) {
                            icon.className =
                                "ri-file-copy-line text-sm";
                        }

                        button.setAttribute(
                            "title",
                            "Copy coupon code"
                        );
                    }, 1200);

                } catch (error) {

                    /*
                     * Clipboard API can be unavailable
                     * when the page is not running in
                     * a secure browser context.
                     */

                    window.prompt(
                        "Copy coupon code:",
                        code
                    );
                }
            }
        );
    });


    /* ==========================================================
       DELETE MODAL
    ========================================================== */

    function openDeleteModal(button) {
        if (
            !deleteModal ||
            !deleteForm ||
            !deleteCode
        ) {
            return;
        }

        const deleteUrl =
            button.dataset.deleteUrl || "#";

        const couponCode =
            button.dataset.couponCode ||
            "this coupon";

        deleteForm.setAttribute(
            "action",
            deleteUrl
        );

        deleteCode.textContent =
            couponCode;

        deleteModal.classList.remove(
            "hidden"
        );

        deleteModal.classList.add(
            "flex"
        );

        deleteModal.setAttribute(
            "aria-hidden",
            "false"
        );

        document.body.classList.add(
            "overflow-hidden"
        );

        window.setTimeout(() => {
            cancelDelete?.focus();
        }, 0);
    }


    function closeDeleteModal() {
        if (
            !deleteModal ||
            !deleteForm ||
            !deleteCode
        ) {
            return;
        }

        deleteModal.classList.add(
            "hidden"
        );

        deleteModal.classList.remove(
            "flex"
        );

        deleteModal.setAttribute(
            "aria-hidden",
            "true"
        );

        deleteForm.setAttribute(
            "action",
            "#"
        );

        deleteCode.textContent =
            "—";

        document.body.classList.remove(
            "overflow-hidden"
        );
    }


    deleteButtons.forEach((button) => {
        button.addEventListener(
            "click",
            () => {
                closeAllMenus();
                openDeleteModal(button);
            }
        );
    });


    cancelDelete?.addEventListener(
        "click",
        closeDeleteModal
    );


    deleteModal?.addEventListener(
        "click",
        (event) => {
            if (
                event.target === deleteModal
            ) {
                closeDeleteModal();
            }
        }
    );


    /* ==========================================================
       GLOBAL CLICK HANDLER
    ========================================================== */

    document.addEventListener(
        "click",
        (event) => {

            /*
             * Close filter panel when clicking
             * outside the filter area.
             */

            if (
                filterPanel &&
                filterButton &&
                !filterPanel.contains(
                    event.target
                ) &&
                !filterButton.contains(
                    event.target
                )
            ) {
                closeFilterPanel();
            }


            /*
             * Detect coupon action menu
             * interactions.
             */

            const clickedMenuButton =
                event.target.closest(
                    ".couponMenuButton"
                );

            const clickedMenu =
                event.target.closest(
                    ".couponActionMenu"
                );


            /*
             * Close all menus when clicking
             * anywhere outside them.
             */

            if (
                !clickedMenuButton &&
                !clickedMenu
            ) {
                closeAllMenus();
            }
        }
    );


    /* ==========================================================
       ESC KEY
    ========================================================== */

    document.addEventListener(
        "keydown",
        (event) => {

            if (event.key !== "Escape") {
                return;
            }

            closeFilterPanel();

            closeAllMenus();


            /*
             * Close delete modal with ESC.
             */

            if (
                deleteModal &&
                !deleteModal.classList.contains(
                    "hidden"
                )
            ) {
                closeDeleteModal();
            }
        }
    );
});