document.addEventListener("DOMContentLoaded", function () {

    /* ============================================================
       CREATE CHAPTER MODAL
    ============================================================ */

    const chapterModal =
        document.getElementById("chapterModal");

    const openChapterModal =
        document.getElementById("openChapterModal");

    const emptyAddChapterBtn =
        document.getElementById("emptyAddChapterBtn");

    const contentCreateChapterBtn =
        document.getElementById("contentCreateChapterBtn");

    const closeChapterModal =
        document.getElementById("closeChapterModal");

    const cancelChapterModal =
        document.getElementById("cancelChapterModal");


    function openChapterModalWindow() {

        if (!chapterModal) {
            return;
        }

        chapterModal.classList.remove("hidden");
        chapterModal.classList.add("flex");

        chapterModal.setAttribute("aria-hidden", "false");

        document.body.classList.add("overflow-hidden");
    }


    function closeChapterModalWindow() {

        if (!chapterModal) {
            return;
        }

        chapterModal.classList.remove("flex");
        chapterModal.classList.add("hidden");

        chapterModal.setAttribute("aria-hidden", "true");

        document.body.classList.remove("overflow-hidden");
    }


    /* ============================================================
       OPEN CREATE CHAPTER MODAL
    ============================================================ */

    if (openChapterModal) {

        openChapterModal.addEventListener(
            "click",
            openChapterModalWindow
        );

    }


    if (emptyAddChapterBtn) {

        emptyAddChapterBtn.addEventListener(
            "click",
            openChapterModalWindow
        );

    }


    if (contentCreateChapterBtn) {

        contentCreateChapterBtn.addEventListener(
            "click",
            openChapterModalWindow
        );

    }


    /* ============================================================
       CLOSE CREATE CHAPTER MODAL
    ============================================================ */

    if (closeChapterModal) {

        closeChapterModal.addEventListener(
            "click",
            closeChapterModalWindow
        );

    }


    if (cancelChapterModal) {

        cancelChapterModal.addEventListener(
            "click",
            closeChapterModalWindow
        );

    }


    /* ============================================================
       CLOSE WHEN CLICKING MODAL BACKDROP
    ============================================================ */

    if (chapterModal) {

        chapterModal.addEventListener(
            "click",
            function (event) {

                if (event.target === chapterModal) {
                    closeChapterModalWindow();
                }

            }
        );

    }


    /* ============================================================
       CLOSE WITH ESCAPE KEY
    ============================================================ */

    document.addEventListener(
        "keydown",
        function (event) {

            if (
                event.key === "Escape" &&
                chapterModal &&
                !chapterModal.classList.contains("hidden")
            ) {

                closeChapterModalWindow();

            }

        }
    );


    /* ============================================================
       SERVER-SIDE NAVIGATION FOR EXISTING ACTION BUTTONS
       ------------------------------------------------------------
       JavaScript does NOT perform validation.

       Django remains responsible for:
       - Validation
       - Authorization
       - Database operations
       - Redirects
       - Permissions
    ============================================================ */

    const navbarActionButtons =
        document.querySelectorAll(
            "[data-navbar-action][data-action-url]"
        );


    navbarActionButtons.forEach(function (button) {

        button.addEventListener(
            "click",
            function () {

                const actionUrl =
                    button.getAttribute("data-action-url");


                if (!actionUrl) {
                    return;
                }


                window.location.href = actionUrl;

            }
        );

    });


    /* ============================================================
       CHAPTER EDIT BUTTON
       ------------------------------------------------------------
       Django provides the URL through data-edit-url.
       JavaScript only performs normal browser navigation.
    ============================================================ */

    const chapterEditButtons =
        document.querySelectorAll(
            ".chapter-edit-button[data-edit-url]"
        );


    chapterEditButtons.forEach(function (button) {

        button.addEventListener(
            "click",
            function () {

                const editUrl =
                    button.getAttribute("data-edit-url");


                if (
                    !editUrl ||
                    editUrl === "#"
                ) {
                    return;
                }


                window.location.href = editUrl;

            }
        );

    });


    /* ============================================================
       DJANGO MESSAGE AUTO DISMISS
       ------------------------------------------------------------
       Django is responsible for creating the messages.

       JavaScript only handles the UI disappearance.

       Messages disappear after 5 seconds:
       - Success
       - Error
       - Warning
       - Info
       - Inline errors
    ============================================================ */

    const djangoMessages =
        document.querySelectorAll(
            '[role="alert"], .django-message'
        );


    djangoMessages.forEach(function (message) {

        setTimeout(
            function () {

                if (
                    !message ||
                    !message.isConnected
                ) {
                    return;
                }


                message.style.transition =
                    "opacity 0.35s ease, transform 0.35s ease";


                message.style.opacity = "0";

                message.style.transform =
                    "translateY(-4px)";


                setTimeout(
                    function () {

                        if (
                            message &&
                            message.isConnected
                        ) {

                            message.remove();

                        }

                    },
                    350
                );

            },
            5000
        );

    });


    /* ============================================================
       CREATE CHAPTER ERROR
       ------------------------------------------------------------
       Django renders the error inside the popup.

       JavaScript only opens the popup.

       NO validation is performed here.
    ============================================================ */

    const chapterCreateInlineError =
        document.getElementById(
            "chapterCreateInlineError"
        );


    if (
        chapterCreateInlineError &&
        chapterModal
    ) {

        chapterModal.classList.remove("hidden");

        chapterModal.classList.add("flex");

        chapterModal.setAttribute(
            "aria-hidden",
            "false"
        );

        document.body.classList.add(
            "overflow-hidden"
        );

    }

});