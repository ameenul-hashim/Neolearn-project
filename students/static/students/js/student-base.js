// ============================================
// STUDENT BASE JS
// ============================================

document.addEventListener("DOMContentLoaded", function () {

    // ============================================
    // ELEMENTS
    // ============================================

    const sidebar = document.getElementById("sidebar");
    const openSidebar = document.getElementById("openSidebar");
    const closeSidebar = document.getElementById("closeSidebar");
    const overlay = document.getElementById("overlay");
    const messageContainer = document.getElementById("messageContainer");


    // ============================================
    // OPEN SIDEBAR
    // ============================================

    if (openSidebar) {
        openSidebar.addEventListener("click", function () {
            sidebar.classList.remove("-translate-x-full");

            if (overlay) {
                overlay.classList.remove("hidden");
            }
        });
    }


    // ============================================
    // CLOSE SIDEBAR BUTTON
    // ============================================

    if (closeSidebar) {
        closeSidebar.addEventListener("click", function () {
            sidebar.classList.add("-translate-x-full");

            if (overlay) {
                overlay.classList.add("hidden");
            }
        });
    }


    // ============================================
    // OVERLAY CLICK
    // ============================================

    if (overlay) {
        overlay.addEventListener("click", function () {
            sidebar.classList.add("-translate-x-full");
            overlay.classList.add("hidden");
        });
    }


    // ============================================
    // ESC KEY CLOSE
    // ============================================

    document.addEventListener("keydown", function (e) {

        if (e.key === "Escape") {

            if (sidebar) {
                sidebar.classList.add("-translate-x-full");
            }

            if (overlay) {
                overlay.classList.add("hidden");
            }

        }

    });


    // ============================================
    // WINDOW RESIZE
    // ============================================

    window.addEventListener("resize", function () {

        if (window.innerWidth >= 1024) {

            if (sidebar) {
                sidebar.classList.remove("-translate-x-full");
            }

            if (overlay) {
                overlay.classList.add("hidden");
            }

        }

    });


    console.log("✅ Student Base JS Loaded");

});