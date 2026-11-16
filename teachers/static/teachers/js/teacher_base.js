/*
 * NeoLearn — Teacher Base Panel
 * Shared controller for the Teacher layout.
 *
 * Responsibilities:
 *   - Save and restore the scroll position of #sidebarScroll.
 *   - Keep the sidebar header and logout area outside the scroll region.
 *   - Control the responsive sidebar.
 *   - Control the Teacher profile dropdown in one place only.
 *   - Control Quick Access search.
 */

(() => {
    "use strict";

    const byId = (id) => document.getElementById(id);

    // --------------------------------------------------
    // SIDEBAR SCROLL POSITION
    // --------------------------------------------------
    const sidebar = byId("sidebar");
    const sidebarScroll = byId("sidebarScroll");
    const sidebarOverlay = byId("sidebarOverlay");
    const menuButton = byId("menuButton");
    const closeSidebarButton = byId("closeSidebar");

    const SIDEBAR_SCROLL_KEY = "neolearn_teacher_sidebar_scroll";
    const isMobile = () => window.matchMedia("(max-width: 1023px)").matches;

    function readSavedScroll() {
        try {
            const savedValue = window.sessionStorage.getItem(SIDEBAR_SCROLL_KEY);
            if (savedValue === null) return null;

            const position = Number.parseInt(savedValue, 10);
            return Number.isFinite(position) && position >= 0 ? position : null;
        } catch (_error) {
            return null;
        }
    }

    function saveSidebarScroll() {
        if (!sidebarScroll) return;

        try {
            window.sessionStorage.setItem(
                SIDEBAR_SCROLL_KEY,
                String(sidebarScroll.scrollTop)
            );
        } catch (_error) {
            // The sidebar remains usable when session storage is unavailable.
        }
    }

    function restoreSidebarScroll() {
        if (!sidebarScroll) return;

        const savedPosition = readSavedScroll();
        if (savedPosition === null) return;

        const maximum = Math.max(
            0,
            sidebarScroll.scrollHeight - sidebarScroll.clientHeight
        );

        sidebarScroll.scrollTop = Math.min(savedPosition, maximum);
    }

    sidebarScroll?.addEventListener("scroll", saveSidebarScroll, { passive: true });

    // Save before a navigation link is followed.
    sidebar?.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) return;

        const link = target.closest("a[href]");
        if (link && sidebar.contains(link)) saveSidebarScroll();
    }, true);

    window.addEventListener("pagehide", saveSidebarScroll);
    window.addEventListener("beforeunload", saveSidebarScroll);

    function scheduleSidebarRestore() {
        restoreSidebarScroll();
        requestAnimationFrame(() => {
            restoreSidebarScroll();
            requestAnimationFrame(restoreSidebarScroll);
        });
    }

    window.addEventListener("pageshow", scheduleSidebarRestore);

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", scheduleSidebarRestore, {
            once: true
        });
    } else {
        scheduleSidebarRestore();
    }

    // --------------------------------------------------
    // RESPONSIVE SIDEBAR OPEN / CLOSE
    // --------------------------------------------------
    function openSidebar() {
        if (!sidebar || !sidebarOverlay || !isMobile()) return;

        sidebar.classList.add("sidebar-open");
        sidebarOverlay.classList.add("overlay-open");
        document.body.classList.add("teacher-sidebar-is-open");

        menuButton?.setAttribute("aria-expanded", "true");
        sidebarOverlay.setAttribute("aria-hidden", "false");
    }

    function closeSidebar() {
        if (!sidebar || !sidebarOverlay) return;

        saveSidebarScroll();
        sidebar.classList.remove("sidebar-open");
        sidebarOverlay.classList.remove("overlay-open");
        document.body.classList.remove("teacher-sidebar-is-open");

        menuButton?.setAttribute("aria-expanded", "false");
        sidebarOverlay.setAttribute("aria-hidden", "true");
    }

    menuButton?.addEventListener("click", openSidebar);
    closeSidebarButton?.addEventListener("click", closeSidebar);
    sidebarOverlay?.addEventListener("click", closeSidebar);

    // Close the mobile drawer after choosing a navigation destination.
    sidebar?.querySelectorAll("nav a[href]").forEach((link) => {
        link.addEventListener("click", () => {
            if (isMobile()) closeSidebar();
        });
    });

    window.addEventListener("resize", () => {
        if (!isMobile()) closeSidebar();
    });

    // --------------------------------------------------
    // TEACHER PROFILE DROPDOWN
    // --------------------------------------------------
    const profileRoot = byId("teacherProfileRoot");
    const profileButton = byId("profileButton");
    const profileDropdown = byId("profileDropdown");

    function setProfileDropdownOpen(open) {
        if (!profileButton || !profileDropdown) return;

        profileDropdown.classList.toggle("hidden", !open);
        profileButton.setAttribute("aria-expanded", open ? "true" : "false");
    }

    function toggleProfileDropdown() {
        if (!profileDropdown) return;

        const isCurrentlyClosed = profileDropdown.classList.contains("hidden");
        setProfileDropdownOpen(isCurrentlyClosed);
    }

    profileButton?.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        toggleProfileDropdown();
    });

    // Clicks inside the menu must not be treated as outside clicks.
    profileDropdown?.addEventListener("click", (event) => {
        event.stopPropagation();
    });

    profileDropdown?.querySelectorAll("a[href]").forEach((link) => {
        link.addEventListener("click", () => setProfileDropdownOpen(false));
    });

    // --------------------------------------------------
    // QUICK ACCESS SEARCH
    // --------------------------------------------------
    const quickAccessRoot = byId("quickAccessRoot");
    const quickAccessInput = byId("quickAccessInput");
    const quickAccessPanel = byId("quickAccessPanel");
    const quickAccessLinks = Array.from(
        document.querySelectorAll("#quickAccessLinks .quick-access-link")
    );
    const quickAccessEmpty = byId("quickAccessEmpty");

    function closeQuickAccess() {
        if (!quickAccessPanel || !quickAccessInput) return;

        quickAccessPanel.hidden = true;
        quickAccessInput.setAttribute("aria-expanded", "false");
    }

    function filterQuickAccess() {
        if (!quickAccessInput) return;

        const query = quickAccessInput.value.trim().toLowerCase();
        let visibleCount = 0;

        quickAccessLinks.forEach((link) => {
            const searchableText =
                `${link.dataset.quickLink || ""} ${link.textContent || ""}`.toLowerCase();

            const isVisible = query === "" || searchableText.includes(query);
            link.hidden = !isVisible;

            if (isVisible) visibleCount += 1;
        });

        quickAccessEmpty?.classList.toggle("hidden", visibleCount !== 0);
    }

    function openQuickAccess() {
        if (!quickAccessPanel || !quickAccessInput) return;

        quickAccessPanel.hidden = false;
        quickAccessInput.setAttribute("aria-expanded", "true");
        filterQuickAccess();
    }

    quickAccessInput?.addEventListener("focus", openQuickAccess);
    quickAccessInput?.addEventListener("click", openQuickAccess);
    quickAccessInput?.addEventListener("input", openQuickAccess);

    quickAccessInput?.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeQuickAccess();
            quickAccessInput.blur();
            return;
        }

        if (event.key === "Enter") {
            const firstVisibleLink = quickAccessLinks.find((link) => !link.hidden);
            if (firstVisibleLink) {
                window.location.assign(firstVisibleLink.href);
            }
        }
    });

    // --------------------------------------------------
    // OUTSIDE CLICK + ESCAPE
    // --------------------------------------------------
    document.addEventListener("click", (event) => {
        const target = event.target;

        if (profileRoot && target instanceof Node && !profileRoot.contains(target)) {
            setProfileDropdownOpen(false);
        }

        if (quickAccessRoot && target instanceof Node && !quickAccessRoot.contains(target)) {
            closeQuickAccess();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeSidebar();
            setProfileDropdownOpen(false);
            closeQuickAccess();
        }

        if (
            (event.ctrlKey || event.metaKey) &&
            event.key.toLowerCase() === "k" &&
            quickAccessInput
        ) {
            event.preventDefault();
            quickAccessInput.focus();
        }
    });

    // Start with the profile menu closed and its accessibility state synchronized.
    setProfileDropdownOpen(false);
})();