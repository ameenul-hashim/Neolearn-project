// ======================================
// TEACHER BASE PANEL JAVASCRIPT
// ======================================

// SIDEBAR

const sidebar = document.getElementById("sidebar");

const sidebarOverlay = document.getElementById("sidebarOverlay");

const menuButton = document.getElementById("menuButton");

const closeSidebar = document.getElementById("closeSidebar");

function openSidebar() {

    if (sidebar) {

        sidebar.classList.remove("-translate-x-full");

    }

    if (sidebarOverlay) {

        sidebarOverlay.classList.remove("hidden");

    }

}

function hideSidebar() {

    if (sidebar) {

        sidebar.classList.add("-translate-x-full");

    }

    if (sidebarOverlay) {

        sidebarOverlay.classList.add("hidden");

    }

}

if (menuButton) {

    menuButton.addEventListener("click", openSidebar);

}

if (closeSidebar) {

    closeSidebar.addEventListener("click", hideSidebar);

}

if (sidebarOverlay) {

    sidebarOverlay.addEventListener("click", hideSidebar);

}

// ======================================
// PROFILE DROPDOWN
// ======================================

const profileButton = document.getElementById("profileButton");

const profileDropdown = document.getElementById("profileDropdown");

if (profileButton && profileDropdown) {

    profileButton.addEventListener("click", function (event) {

        event.stopPropagation();

        profileDropdown.classList.toggle("hidden");

    });

    document.addEventListener("click", function () {

        profileDropdown.classList.add("hidden");

    });

}

// ======================================
// ESC KEY CLOSE
// ======================================

document.addEventListener("keydown", function (event) {

    if (event.key === "Escape") {

        hideSidebar();

        if (profileDropdown) {

            profileDropdown.classList.add("hidden");

        }

    }

});

// ======================================
// ACTIVE MENU (OPTIONAL)
// ======================================

const currentPath = window.location.pathname;

const menuLinks = document.querySelectorAll("aside nav a");

menuLinks.forEach((link) => {

    if (link.getAttribute("href") === currentPath) {

        link.classList.add(
            "bg-cyan-400/10",
            "border-l-4",
            "border-cyan-400",
            "text-white"
        );

    }

});