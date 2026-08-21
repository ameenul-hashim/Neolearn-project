document.addEventListener("DOMContentLoaded", function () {

    // =========================================================
    // COURSE BUILDER JS
    //
    // ONLY SMALL FRONTEND INTERACTIONS.
    //
    // Django handles:
    // - database
    // - views
    // - validation
    // - permissions
    // - chapter selection
    // - content URLs
    // - video/PDF/quiz/live data
    //
    // NO AJAX
    // NO FETCH
    // NO DATABASE LOGIC
    // =========================================================


    // =========================================================
    // CHAPTER CREATE MODAL
    // =========================================================

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


    // =========================================================
    // OPEN CHAPTER CREATE MODAL
    // =========================================================

    function openChapterModalWindow() {

        if (!chapterModal) {
            return;
        }

        chapterModal.classList.remove("hidden");
        chapterModal.classList.add("flex");

        document.body.classList.add("overflow-hidden");


        const chapterNameInput =
            document.getElementById("chapter_name");


        if (chapterNameInput) {

            window.setTimeout(function () {

                chapterNameInput.focus();

            }, 100);

        }

    }


    // =========================================================
    // CLOSE CHAPTER CREATE MODAL
    // =========================================================

    function closeChapterModalWindow() {

        if (!chapterModal) {
            return;
        }

        chapterModal.classList.remove("flex");
        chapterModal.classList.add("hidden");

        document.body.classList.remove("overflow-hidden");

    }


    // =========================================================
    // OPEN BUTTON
    // =========================================================

    if (openChapterModal) {

        openChapterModal.addEventListener(
            "click",
            openChapterModalWindow
        );

    }


    // =========================================================
    // EMPTY CURRICULUM BUTTON
    // =========================================================

    if (emptyAddChapterBtn) {

        emptyAddChapterBtn.addEventListener(
            "click",
            openChapterModalWindow
        );

    }


    // =========================================================
    // EMPTY RIGHT WORKSPACE BUTTON
    // =========================================================

    if (contentCreateChapterBtn) {

        contentCreateChapterBtn.addEventListener(
            "click",
            openChapterModalWindow
        );

    }


    // =========================================================
    // CLOSE BUTTON
    // =========================================================

    if (closeChapterModal) {

        closeChapterModal.addEventListener(
            "click",
            closeChapterModalWindow
        );

    }


    // =========================================================
    // CANCEL BUTTON
    // =========================================================

    if (cancelChapterModal) {

        cancelChapterModal.addEventListener(
            "click",
            closeChapterModalWindow
        );

    }


    // =========================================================
    // CLICK MODAL BACKDROP
    // =========================================================

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


    // =========================================================
    // TEACHERS MODAL
    // =========================================================

    const teachersModal =
        document.getElementById("teachersModal");

    const viewTeachersBtn =
        document.getElementById("viewTeachersBtn");

    const closeTeachersModal =
        document.getElementById("closeTeachersModal");


    // =========================================================
    // OPEN TEACHERS MODAL
    // =========================================================

    function openTeachersModal() {

        if (!teachersModal) {
            return;
        }

        teachersModal.classList.remove("hidden");
        teachersModal.classList.add("flex");

        document.body.classList.add("overflow-hidden");

    }


    // =========================================================
    // CLOSE TEACHERS MODAL
    // =========================================================

    function closeTeachersModalWindow() {

        if (!teachersModal) {
            return;
        }

        teachersModal.classList.remove("flex");
        teachersModal.classList.add("hidden");

        document.body.classList.remove("overflow-hidden");

    }


    // =========================================================
    // VIEW TEACHERS
    // =========================================================

    if (viewTeachersBtn) {

        viewTeachersBtn.addEventListener(
            "click",
            openTeachersModal
        );

    }


    // =========================================================
    // CLOSE TEACHERS
    // =========================================================

    if (closeTeachersModal) {

        closeTeachersModal.addEventListener(
            "click",
            closeTeachersModalWindow
        );

    }


    // =========================================================
    // TEACHERS MODAL BACKDROP
    // =========================================================

    if (teachersModal) {

        teachersModal.addEventListener(
            "click",
            function (event) {

                if (event.target === teachersModal) {

                    closeTeachersModalWindow();

                }

            }
        );

    }


    // =========================================================
    // CHAPTER CARD CLICK
    //
    // There is NO open/close accordion anymore.
    //
    // When a teacher clicks anywhere on a chapter card,
    // Django opens that chapter in the right workspace.
    //
    // The selected chapter remains expanded on the left.
    //
    // These remain independent:
    // - Edit
    // - Delete request
    // - Timeline eye
    // - Video
    // - PDF
    // - Quiz
    // - Live
    // =========================================================

    const chapterItems =
        document.querySelectorAll(".chapter-item");


    chapterItems.forEach(function (chapterItem) {

        chapterItem.addEventListener(
            "click",
            function (event) {

                const clickedElement =
                    event.target;


                // -------------------------------------------------
                // Do not interfere with buttons.
                // -------------------------------------------------

                if (
                    clickedElement.closest("button")
                ) {

                    return;

                }


                // -------------------------------------------------
                // Do not interfere with content links.
                //
                // Videos
                // PDFs
                // Quizzes
                // Live Classes
                // -------------------------------------------------

                if (
                    clickedElement.closest(
                        ".content-type-link"
                    )
                ) {

                    return;

                }


                // -------------------------------------------------
                // Do not interfere with timeline eye.
                // -------------------------------------------------

                if (
                    clickedElement.closest(
                        ".chapter-timeline-link"
                    )
                ) {

                    return;

                }


                // -------------------------------------------------
                // Do not interfere with normal Django anchors.
                //
                // Chapter name
                // Edit
                // Delete request
                // -------------------------------------------------

                if (
                    clickedElement.closest("a")
                ) {

                    return;

                }


                // -------------------------------------------------
                // Find the chapter URL from the chapter name link.
                // -------------------------------------------------

                const chapterLink =
                    chapterItem.querySelector(
                        'a[href*="/chapter/"]'
                    );


                if (!chapterLink) {
                    return;
                }


                // -------------------------------------------------
                // Normal Django navigation.
                // -------------------------------------------------

                window.location.href =
                    chapterLink.href;

            }
        );

    });


    // =========================================================
    // CHAPTER ACTION LINKS
    //
    // Edit
    // Delete Request
    //
    // Normal Django navigation.
    // =========================================================

    const chapterActionLinks =
        document.querySelectorAll(
            ".chapter-item a"
        );


    chapterActionLinks.forEach(function (link) {

        link.addEventListener(
            "click",
            function (event) {

                event.stopPropagation();

            }
        );

    });


    // =========================================================
    // CONTENT LINKS
    //
    // Video
    // PDF
    // Quiz
    // Live
    //
    // Normal Django navigation.
    //
    // No AJAX.
    // No fetch().
    // No JavaScript workspace rendering.
    //
    // The URL opens the correct right-side workspace.
    // =========================================================

    const contentLinks =
        document.querySelectorAll(
            ".content-type-link"
        );


    contentLinks.forEach(function (link) {

        link.addEventListener(
            "click",
            function (event) {

                /*
                 * Stop the click from reaching the chapter card.
                 *
                 * IMPORTANT:
                 * We DO NOT use preventDefault().
                 *
                 * Therefore the Django URL opens normally.
                 */

                event.stopPropagation();

            }
        );

    });


    // =========================================================
    // CHAPTER TIMELINE EYE
    //
    // The Timeline link is a normal Django <a>.
    //
    // We explicitly navigate to the href generated by Django.
    //
    // Django remains responsible for:
    // - chapter selection
    // - timeline condition
    // - permissions
    // - database data
    // =========================================================

    const timelineLinks =
        document.querySelectorAll(
            ".chapter-timeline-link"
        );

    timelineLinks.forEach(function (link) {

        link.addEventListener(
            "click",
            function (event) {

                event.preventDefault();
                event.stopPropagation();

                const timelineUrl =
                    link.getAttribute("href");

                if (!timelineUrl) {
                    return;
                }

                window.location.assign(
                    timelineUrl
                );

            }
        );

    });


    // =========================================================
    // ESC KEY
    //
    // ESC closes MODALS only.
    //
    // It does NOT close a chapter.
    // It does NOT collapse curriculum content.
    // =========================================================

    document.addEventListener(
        "keydown",
        function (event) {

            if (event.key !== "Escape") {
                return;
            }


            // -----------------------------------------------------
            // Chapter create modal
            // -----------------------------------------------------

            if (
                chapterModal &&
                chapterModal.classList.contains("flex")
            ) {

                closeChapterModalWindow();

            }


            // -----------------------------------------------------
            // Teachers modal
            // -----------------------------------------------------

            if (
                teachersModal &&
                teachersModal.classList.contains("flex")
            ) {

                closeTeachersModalWindow();

            }

        }
    );

});