document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const searchInput = document.getElementById('searchInput');
    const clearSearch = document.getElementById('clearSearch');
    const courseCards = document.querySelectorAll('.course-card');
    const categoryChips = document.querySelectorAll('.category-chip');
    const resultsCount = document.getElementById('resultsCount');
    const totalCourses = document.getElementById('totalCourses');
    const filterToggle = document.getElementById('filterToggle');
    const filterPanel = document.getElementById('filterPanel');
    const applyFiltersBtn = document.getElementById('applyFilters');
    const resetFiltersBtn = document.getElementById('resetFilters');
    const courseGrid = document.getElementById('courseGrid');
    const priceMin = document.getElementById('priceMin');
    const priceMax = document.getElementById('priceMax');
    
    // State
    let currentCategory = 'all';
    let currentSearch = '';
    let currentSort = 'newest';
    let activeStatusFilters = [];
    let activeDiscountFilters = [];
    let isFilterPanelOpen = false;
    
    // ===== FILTER PANEL TOGGLE =====
    function openFilterPanel() {
        filterPanel.classList.remove('opacity-0', 'pointer-events-none');
        filterPanel.querySelector('.translate-x-full').classList.remove('translate-x-full');
        document.body.style.overflow = 'hidden';
        isFilterPanelOpen = true;
    }
    
    window.closeFilters = function() {
        filterPanel.classList.add('opacity-0', 'pointer-events-none');
        filterPanel.querySelector('.translate-x-full').classList.add('translate-x-full');
        document.body.style.overflow = '';
        isFilterPanelOpen = false;
    };
    
    filterToggle.addEventListener('click', function(e) {
        e.stopPropagation();
        if (isFilterPanelOpen) {
            closeFilters();
        } else {
            openFilterPanel();
        }
    });
    
    // Close panel when clicking outside (on backdrop)
    document.querySelector('#filterPanel .absolute.inset-0')?.addEventListener('click', function() {
        closeFilters();
    });
    
    // ===== SORT RADIO BUTTONS =====
    document.querySelectorAll('input[name="sort"]').forEach(radio => {
        radio.addEventListener('change', function() {
            currentSort = this.value;
            filterAndSortCourses();
        });
    });
    
    // ===== LIVE SEARCH =====
    searchInput.addEventListener('input', function() {
        currentSearch = this.value.toLowerCase().trim();
        clearSearch.classList.toggle('hidden', !currentSearch);
        filterAndSortCourses();
    });
    
    // ===== CLEAR SEARCH =====
    clearSearch.addEventListener('click', function() {
        searchInput.value = '';
        currentSearch = '';
        this.classList.add('hidden');
        filterAndSortCourses();
        searchInput.focus();
    });
    
    // ===== CATEGORY CHIPS =====
    categoryChips.forEach(chip => {
        chip.addEventListener('click', function() {
            categoryChips.forEach(c => c.classList.remove('active', 'bg-cyan-500', 'text-black'));
            categoryChips.forEach(c => c.classList.add('bg-[#111827]', 'text-slate-300'));
            this.classList.add('active', 'bg-cyan-500', 'text-black');
            this.classList.remove('bg-[#111827]', 'text-slate-300');
            currentCategory = this.dataset.category;
            filterAndSortCourses();
        });
    });
    
    // ===== APPLY FILTERS =====
    applyFiltersBtn.addEventListener('click', function() {
        // Get status filters
        activeStatusFilters = [];
        document.querySelectorAll('.filter-status:checked').forEach(cb => {
            activeStatusFilters.push(cb.value);
        });
        
        // Get discount filters
        activeDiscountFilters = [];
        document.querySelectorAll('.filter-discount:checked').forEach(cb => {
            activeDiscountFilters.push(cb.value);
        });
        
        filterAndSortCourses();
        closeFilters();
    });
    
    // ===== RESET FILTERS =====
    resetFiltersBtn.addEventListener('click', function() {
        // Reset search
        searchInput.value = '';
        currentSearch = '';
        clearSearch.classList.add('hidden');
        
        // Reset category
        categoryChips.forEach(c => {
            c.classList.remove('active', 'bg-cyan-500', 'text-black');
            c.classList.add('bg-[#111827]', 'text-slate-300');
        });
        document.querySelector('.category-chip[data-category="all"]')?.classList.add('active', 'bg-cyan-500', 'text-black');
        currentCategory = 'all';
        
        // Reset sort
        document.querySelector('input[name="sort"][value="newest"]').checked = true;
        currentSort = 'newest';
        
        // Reset filter checkboxes
        document.querySelectorAll('.filter-status, .filter-discount').forEach(cb => cb.checked = false);
        activeStatusFilters = [];
        activeDiscountFilters = [];
        
        // Reset price range
        priceMin.value = '';
        priceMax.value = '';
        
        filterAndSortCourses();
        // Don't close filters after reset so user can see cleared state
    });
    
    // ===== MAIN FILTER + SORT FUNCTION =====
    function filterAndSortCourses() {
        // Reset all cards to visible first
        courseCards.forEach(card => {
            card.style.display = '';
        });
        
        let visibleCards = [];
        
        courseCards.forEach(card => {
            const name = card.dataset.name || '';
            const categories = card.dataset.category || '';
            const status = card.dataset.status || '';
            const discount = parseFloat(card.dataset.discount) || 0;
            const discountType = card.dataset.discountType || '';
            const offerActive = card.dataset.offerActive === 'true';
            const price = parseFloat(card.dataset.price) || 0;
            
            // Search filter
            let matchesSearch = !currentSearch || name.includes(currentSearch);
            
            // Category filter
            let matchesCategory = currentCategory === 'all' || categories.includes(currentCategory);
            
            // Status filter
            let matchesStatus = true;
            if (activeStatusFilters.length > 0) {
                matchesStatus = activeStatusFilters.includes(status);
            }
            
            // Discount filter
            let matchesDiscount = true;
            if (activeDiscountFilters.length > 0) {
                const hasDiscount = discount > 0 && offerActive;
                const isPercentage = activeDiscountFilters.includes('percentage') && hasDiscount && discountType === 'percentage';
                const isFixed = activeDiscountFilters.includes('fixed') && hasDiscount && discountType === 'fixed';
                const isNoOffer = activeDiscountFilters.includes('no_offer') && !hasDiscount;
                matchesDiscount = isPercentage || isFixed || isNoOffer;
            }
            
            // Price range filter
            let matchesPrice = true;
            const minVal = priceMin.value ? parseFloat(priceMin.value) : null;
            const maxVal = priceMax.value ? parseFloat(priceMax.value) : null;
            if (minVal !== null) {
                matchesPrice = matchesPrice && price >= minVal;
            }
            if (maxVal !== null) {
                matchesPrice = matchesPrice && price <= maxVal;
            }
            
            if (matchesSearch && matchesCategory && matchesStatus && matchesDiscount && matchesPrice) {
                card.style.display = '';
                visibleCards.push(card);
            } else {
                card.style.display = 'none';
            }
        });
        
        // Sort visible cards
        const sortedCards = sortCards(visibleCards, currentSort);
        
        // Re-append sorted cards
        sortedCards.forEach(card => courseGrid.appendChild(card));
        
        // Update counts
        const count = sortedCards.length;
        resultsCount.textContent = `Showing ${count} Course${count !== 1 ? 's' : ''}`;
        if (totalCourses) {
            totalCourses.textContent = `${count} Courses`;
        }
    }
    
    // ===== SORTING LOGIC =====
    function sortCards(cards, sortType) {
        return cards.sort((a, b) => {
            const aName = a.dataset.name || '';
            const bName = b.dataset.name || '';
            const aPrice = parseFloat(a.dataset.price) || 0;
            const bPrice = parseFloat(b.dataset.price) || 0;
            const aDiscount = parseFloat(a.dataset.discount) || 0;
            const bDiscount = parseFloat(b.dataset.discount) || 0;
            const aId = parseInt(a.dataset.id) || 0;
            const bId = parseInt(b.dataset.id) || 0;
            
            switch(sortType) {
                case 'a_z': return aName.localeCompare(bName);
                case 'z_a': return bName.localeCompare(aName);
                case 'price_low': return aPrice - bPrice;
                case 'price_high': return bPrice - aPrice;
                case 'discount': return bDiscount - aDiscount;
                case 'newest': return bId - aId;
                case 'oldest': return aId - bId;
                default: return 0;
            }
        });
    }
    
    // // ===== CARD CLICK =====
    // document.querySelectorAll('.course-card').forEach(card => {
    //     card.addEventListener('click', function(e) {
    //         if (e.target.closest('.wishlist-btn') || e.target.closest('.add-to-cart')) {
    //             return;
    //         }
    //         const id = this.dataset.id;
    //         if (id) {
    //             window.location.href = `/marketplace/${id}/`;
    //         }
    //     });
    // });
    
  // ===== WISHLIST TOGGLE =====

const csrfToken = document.getElementById("csrf-token").value;

document.querySelectorAll(".wishlist-btn").forEach((button) => {

    button.addEventListener("click", async function (e) {

        e.preventDefault();
        e.stopPropagation();

        const batchId = this.dataset.batchId;
        const icon = this.querySelector(".wishlist-icon");

        try {

            const response = await fetch(`/students/wishlist/toggle/${batchId}/`, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken,
                    "X-Requested-With": "XMLHttpRequest",
                },
            });

            const data = await response.json();

            if (!data.success) {
                return;
            }

            if (data.wishlisted) {

                icon.classList.remove("ri-heart-3-line", "text-gray-400");
                icon.classList.add("ri-heart-3-fill", "text-red-500");

                icon.style.animation = "heart-pulse .5s";

                setTimeout(() => {
                    icon.style.animation = "";
                }, 500);

            } else {

                icon.classList.remove("ri-heart-3-fill", "text-red-500");
                icon.classList.add("ri-heart-3-line", "text-gray-400");

            }

        } catch (error) {

            console.error("Wishlist Error:", error);

        }

    });

});
    
    // ===== ADD TO CART =====
    document.querySelectorAll('.add-to-cart').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const originalText = this.innerHTML;
            const originalClasses = this.className;
            this.innerHTML = '✔ Added';
            this.className = 'w-full py-2 rounded-full bg-emerald-500 text-white text-sm font-bold transition-all duration-300 scale-105 shadow-lg';
            
            setTimeout(() => {
                this.innerHTML = originalText;
                this.className = originalClasses;
            }, 2000);
        });
    });
    
    // ===== KEYBOARD SHORTCUTS =====
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && isFilterPanelOpen) {
            closeFilters();
        }
        if (e.key === '/' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            searchInput.focus();
        }
    });
    
    // Initial load
    filterAndSortCourses();
    console.log('🚀 Marketplace initialized');
});

// Add heart pulse animation
const style = document.createElement('style');
style.textContent = `
    @keyframes heart-pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.3); }
        100% { transform: scale(1); }
    }
`;
document.head.appendChild(style);
