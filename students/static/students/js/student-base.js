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
    // RESPONSIVE BREAKPOINT
    // Tailwind lg = 1024px
    // ============================================

    const DESKTOP_BREAKPOINT = 1024;


    // ============================================
    // OPEN SIDEBAR
    // ============================================

    function openSidebarMenu() {

        if (!sidebar) {
            return;
        }

        sidebar.classList.remove("-translate-x-full");

        if (overlay && window.innerWidth < DESKTOP_BREAKPOINT) {
            overlay.classList.remove("hidden");
        }
    }


    // ============================================
    // CLOSE SIDEBAR
    // ============================================

    function closeSidebarMenu() {

        if (sidebar) {
            sidebar.classList.add("-translate-x-full");
        }

        if (overlay) {
            overlay.classList.add("hidden");
        }
    }


    // ============================================
    // DESKTOP SIDEBAR STATE
    // ============================================

    function updateSidebarForViewport() {

        if (!sidebar) {
            return;
        }


        // --------------------------------------------
        // DESKTOP
        // --------------------------------------------

        if (window.innerWidth >= DESKTOP_BREAKPOINT) {

            sidebar.classList.remove("-translate-x-full");

            if (overlay) {
                overlay.classList.add("hidden");
            }

            return;
        }


        // --------------------------------------------
        // MOBILE / TABLET
        // --------------------------------------------

        sidebar.classList.add("-translate-x-full");

        if (overlay) {
            overlay.classList.add("hidden");
        }
    }


    // ============================================
    // OPEN SIDEBAR BUTTON
    // ============================================

    if (openSidebar) {

        openSidebar.addEventListener("click", function () {

            openSidebarMenu();

        });

    }


    // ============================================
    // CLOSE SIDEBAR BUTTON
    // ============================================

    if (closeSidebar) {

        closeSidebar.addEventListener("click", function () {

            closeSidebarMenu();

        });

    }


    // ============================================
    // OVERLAY CLICK
    // ============================================

    if (overlay) {

        overlay.addEventListener("click", function () {

            closeSidebarMenu();

        });

    }


    // ============================================
    // ESC KEY CLOSE
    // ============================================

    document.addEventListener("keydown", function (e) {

        if (e.key === "Escape") {

            closeSidebarMenu();

        }

    });


    // ============================================
    // WINDOW RESIZE
    // ============================================

    let resizeTimer = null;

    window.addEventListener("resize", function () {

        clearTimeout(resizeTimer);

        resizeTimer = setTimeout(function () {

            updateSidebarForViewport();

        }, 100);

    });


    // ============================================
    // INITIAL RESPONSIVE STATE
    // ============================================

    updateSidebarForViewport();


    // ============================================
    // MESSAGE CONTAINER
    // Reserved for shared message system.
    // Existing toast-messages.js handles messages.
    // ============================================

    if (messageContainer) {

        // Intentionally no additional behavior here.
        // Keep message functionality handled by
        // the existing shared toast system.

    }


    // ============================================
    // DEBUG
    // ============================================

    console.log("✅ Student Base JS Loaded");

});