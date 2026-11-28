// ============================================================
// NEOLEARN STUDENT BASE
// Responsive sidebar + desktop collapse + independent scroll memory
// ============================================================

document.addEventListener("DOMContentLoaded", function () {
    "use strict";

    const body = document.body;
    const sidebar = document.getElementById("sidebar");
    const sidebarScroll = document.getElementById("sidebarScroll");
    const appMain = document.getElementById("appMain");
    const topbar = document.getElementById("studentTopbar");

    const openSidebarButton = document.getElementById("openSidebar");
    const closeSidebarButton = document.getElementById("closeSidebar");
    const toggleSidebarButton = document.getElementById("toggleSidebar");
    const toggleSidebarIcon = document.getElementById("sidebarToggleIcon");
    const overlay = document.getElementById("overlay");

    // The main scrolling element is the <main> content region, not the window.
    const mainContent = document.querySelector("#appMain main");
    const DESKTOP_BREAKPOINT = 1024;

    const SIDEBAR_SCROLL_KEY = "neolearner_student_sidebar_scroll_v4";
    const MAIN_SCROLL_PREFIX = "neolearner_student_main_scroll_v4:";
    const COLLAPSED_KEY = "neolearner_student_sidebar_collapsed_v2";

    let resizeTimer = null;
    let restoreAttempts = 0;
    let restoreFinished = false;
    let userInteractedWithScroll = false;

    if ("scrollRestoration" in window.history) {
        window.history.scrollRestoration = "manual";
    }

    function storageGet(key) {
        try {
            return window.sessionStorage.getItem(key);
        } catch (error) {
            return null;
        }
    }

    function storageSet(key, value) {
        try {
            window.sessionStorage.setItem(key, String(value));
        } catch (error) {
            // Continue normally when browser storage is unavailable.
        }
    }

    function currentMainScrollKey() {
        return MAIN_SCROLL_PREFIX + window.location.pathname + window.location.search;
    }

    function saveScrollPositions() {
        if (sidebarScroll) {
            storageSet(SIDEBAR_SCROLL_KEY, sidebarScroll.scrollTop);
        }

        if (mainContent) {
            storageSet(currentMainScrollKey(), mainContent.scrollTop);
        }
    }

    function restoreScrollPositions() {
        if (restoreFinished || userInteractedWithScroll || restoreAttempts >= 24) {
            return;
        }

        restoreAttempts += 1;

        const savedSidebar = Number(storageGet(SIDEBAR_SCROLL_KEY) || 0);
        const savedMain = Number(storageGet(currentMainScrollKey()) || 0);

        if (sidebarScroll && Number.isFinite(savedSidebar)) {
            sidebarScroll.scrollTop = savedSidebar;
        }

        if (mainContent && Number.isFinite(savedMain)) {
            mainContent.scrollTop = savedMain;
        }

        const sidebarStillWaiting =
            sidebarScroll &&
            savedSidebar > 0 &&
            sidebarScroll.scrollTop < Math.min(savedSidebar, sidebarScroll.scrollHeight);

        const mainStillWaiting =
            mainContent &&
            savedMain > 0 &&
            mainContent.scrollTop < Math.min(savedMain, mainContent.scrollHeight);

        // Retry while layout/images are still settling. Stop after a bounded period.
        if (sidebarStillWaiting || mainStillWaiting) {
            window.requestAnimationFrame(restoreScrollPositions);
        } else if (document.readyState === "complete" || restoreAttempts >= 8) {
            restoreFinished = true;
        } else {
            window.requestAnimationFrame(restoreScrollPositions);
        }
    }

    if (sidebarScroll) {
        sidebarScroll.addEventListener("scroll", function () {
            storageSet(SIDEBAR_SCROLL_KEY, sidebarScroll.scrollTop);
        }, { passive: true });

        sidebarScroll.addEventListener("wheel", function () {
            userInteractedWithScroll = true;
        }, { passive: true });

        sidebarScroll.addEventListener("touchstart", function () {
            userInteractedWithScroll = true;
        }, { passive: true });
    }

    if (mainContent) {
        mainContent.addEventListener("scroll", function () {
            storageSet(currentMainScrollKey(), mainContent.scrollTop);
        }, { passive: true });

        mainContent.addEventListener("wheel", function () {
            userInteractedWithScroll = true;
        }, { passive: true });

        mainContent.addEventListener("touchstart", function () {
            userInteractedWithScroll = true;
        }, { passive: true });
    }

    // Save positions before same-tab navigation.
    document.addEventListener("click", function (event) {
        const target = event.target instanceof Element ? event.target : null;
        if (!target) return;

        const link = target.closest("a[href]");
        if (!link) return;

        const href = link.getAttribute("href");
        if (
            !href ||
            href === "#" ||
            href.startsWith("javascript:") ||
            link.target === "_blank" ||
            event.defaultPrevented ||
            event.button !== 0 ||
            event.ctrlKey ||
            event.metaKey ||
            event.shiftKey ||
            event.altKey
        ) {
            return;
        }

        saveScrollPositions();
    }, true);

    document.addEventListener("keydown", function (event) {
        if (event.key !== "Enter") return;

        const target = event.target instanceof Element ? event.target : null;
        const link = target ? target.closest("a[href]") : null;

        if (link) saveScrollPositions();
    }, true);

    window.addEventListener("beforeunload", saveScrollPositions);
    window.addEventListener("pagehide", saveScrollPositions);

    // Restore after DOM creation and after images/layout have had time to settle.
    window.requestAnimationFrame(restoreScrollPositions);
    window.addEventListener("load", restoreScrollPositions, { once: true });
    window.setTimeout(restoreScrollPositions, 100);
    window.setTimeout(restoreScrollPositions, 250);
    window.setTimeout(restoreScrollPositions, 500);

    // ------------------------------------------------------------
    // Desktop sidebar: expanded <-> icon-only
    // ------------------------------------------------------------

    function setDesktopCollapsed(collapsed, persist) {
        if (!body || window.innerWidth < DESKTOP_BREAKPOINT) return;

        body.classList.toggle("student-sidebar-collapsed", collapsed);

        if (toggleSidebarButton) {
            toggleSidebarButton.setAttribute("aria-expanded", String(!collapsed));
            toggleSidebarButton.setAttribute(
                "aria-label",
                collapsed ? "Open sidebar" : "Collapse sidebar"
            );
            toggleSidebarButton.setAttribute(
                "title",
                collapsed ? "Open sidebar" : "Collapse sidebar"
            );
        }

        if (toggleSidebarIcon) {
            toggleSidebarIcon.className = collapsed
                ? "ri-arrow-right-s-line text-[20px]"
                : "ri-arrow-left-s-line text-[20px]";
        }

        if (persist) {
            storageSet(COLLAPSED_KEY, collapsed ? "1" : "0");
        }
    }

    function restoreDesktopSidebarState() {
        if (window.innerWidth < DESKTOP_BREAKPOINT) {
            body.classList.remove("student-sidebar-collapsed");
            return;
        }

        const shouldCollapse = storageGet(COLLAPSED_KEY) === "1";
        setDesktopCollapsed(shouldCollapse, false);
    }

    if (toggleSidebarButton) {
        toggleSidebarButton.addEventListener("click", function (event) {
            event.preventDefault();

            if (window.innerWidth < DESKTOP_BREAKPOINT) return;

            const currentlyCollapsed =
                body.classList.contains("student-sidebar-collapsed");

            setDesktopCollapsed(!currentlyCollapsed, true);
        });
    }

    // ------------------------------------------------------------
    // Mobile sidebar: off-canvas open / close
    // ------------------------------------------------------------

    function openMobileSidebar() {
        if (!sidebar || window.innerWidth >= DESKTOP_BREAKPOINT) return;

        sidebar.classList.remove("-translate-x-full");

        if (overlay) overlay.classList.remove("hidden");

        if (openSidebarButton) {
            openSidebarButton.setAttribute("aria-expanded", "true");
        }
    }

    function closeMobileSidebar() {
        if (window.innerWidth >= DESKTOP_BREAKPOINT) return;

        if (sidebar) sidebar.classList.add("-translate-x-full");
        if (overlay) overlay.classList.add("hidden");

        if (openSidebarButton) {
            openSidebarButton.setAttribute("aria-expanded", "false");
        }
    }

    function updateSidebarForViewport() {
        if (!sidebar) return;

        if (window.innerWidth >= DESKTOP_BREAKPOINT) {
            sidebar.classList.remove("-translate-x-full");

            if (overlay) overlay.classList.add("hidden");

            if (openSidebarButton) {
                openSidebarButton.setAttribute("aria-expanded", "false");
            }

            restoreDesktopSidebarState();
        } else {
            body.classList.remove("student-sidebar-collapsed");
            sidebar.classList.add("-translate-x-full");

            if (overlay) overlay.classList.add("hidden");

            if (openSidebarButton) {
                openSidebarButton.setAttribute("aria-expanded", "false");
            }
        }
    }

    if (openSidebarButton) {
        openSidebarButton.addEventListener("click", openMobileSidebar);
    }

    if (closeSidebarButton) {
        closeSidebarButton.addEventListener("click", closeMobileSidebar);
    }

    if (overlay) {
        overlay.addEventListener("click", closeMobileSidebar);
    }

    if (sidebar) {
        sidebar.addEventListener("click", function (event) {
            const target = event.target instanceof Element ? event.target : null;
            if (!target || window.innerWidth >= DESKTOP_BREAKPOINT) return;

            const link = target.closest("a[href]");
            if (link) closeMobileSidebar();
        });
    }

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") closeMobileSidebar();
    });

    window.addEventListener("resize", function () {
        window.clearTimeout(resizeTimer);
        resizeTimer = window.setTimeout(updateSidebarForViewport, 120);
    });

    updateSidebarForViewport();

    // Keep references explicit for easier debugging in the browser console.
    void appMain;
    void topbar;

    // toast-messages.js remains the single shared message handler.
    console.log("NeoLearn Student Base JS loaded.");
});