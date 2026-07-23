document.addEventListener("DOMContentLoaded", function () {

    // =====================================================
    // CHAPTER MODAL
    // =====================================================

    const chapterModal = document.getElementById("chapterModal");
    const openChapterModal = document.getElementById("openChapterModal");
    const closeChapterModal = document.getElementById("closeChapterModal");
    const cancelChapterModal = document.getElementById("cancelChapterModal");

    function openChapter() {

        if (!chapterModal) return;

        chapterModal.classList.remove("hidden");
        chapterModal.classList.add("flex");

        document.body.classList.add("overflow-hidden");
    }

    function closeChapter() {

        if (!chapterModal) return;

        chapterModal.classList.remove("flex");
        chapterModal.classList.add("hidden");

        document.body.classList.remove("overflow-hidden");
    }

    if (openChapterModal) {
        openChapterModal.addEventListener("click", openChapter);
    }

    if (closeChapterModal) {
        closeChapterModal.addEventListener("click", closeChapter);
    }

    if (cancelChapterModal) {
        cancelChapterModal.addEventListener("click", closeChapter);
    }

    if (chapterModal) {

        chapterModal.addEventListener("click", function (e) {

            if (e.target === chapterModal) {

                closeChapter();

            }

        });

    }


    // =====================================================
    // TEACHERS MODAL
    // =====================================================

    const teachersModal = document.getElementById("teachersModal");
    const viewTeachersBtn = document.getElementById("viewTeachersBtn");
    const closeTeachersModal = document.getElementById("closeTeachersModal");

    function openTeachers() {

        if (!teachersModal) return;

        teachersModal.classList.remove("hidden");
        teachersModal.classList.add("flex");

        document.body.classList.add("overflow-hidden");
    }

    function closeTeachers() {

        if (!teachersModal) return;

        teachersModal.classList.remove("flex");
        teachersModal.classList.add("hidden");

        document.body.classList.remove("overflow-hidden");
    }

    if (viewTeachersBtn) {
        viewTeachersBtn.addEventListener("click", openTeachers);
    }

    if (closeTeachersModal) {
        closeTeachersModal.addEventListener("click", closeTeachers);
    }

    if (teachersModal) {

        teachersModal.addEventListener("click", function (e) {

            if (e.target === teachersModal) {

                closeTeachers();

            }

        });

    }


    // =====================================================
    // ESC KEY
    // =====================================================

    document.addEventListener("keydown", function (e) {

        if (e.key !== "Escape") return;

        if (chapterModal && chapterModal.classList.contains("flex")) {
            closeChapter();
        }

        if (teachersModal && teachersModal.classList.contains("flex")) {
            closeTeachers();
        }

    });

});