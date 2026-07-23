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
// AUTO DISMISS DJANGO MESSAGES
// ============================================

if (messageContainer) {

    const messages = messageContainer.querySelectorAll(".message-item");

    setTimeout(function () {

        messages.forEach(function (message) {

            message.style.transition =
                "opacity .45s ease, transform .45s ease, max-height .45s ease, margin .45s ease, padding .45s ease";

            message.style.opacity = "0";
            message.style.transform = "translateX(30px) scale(.96)";
            message.style.maxHeight = "0";
            message.style.marginBottom = "0";
            message.style.paddingTop = "0";
            message.style.paddingBottom = "0";

            setTimeout(function () {

                message.remove();

                if (!messageContainer.children.length) {
                    messageContainer.remove();
                }

            }, 450);

        });

    }, 3000);

}

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