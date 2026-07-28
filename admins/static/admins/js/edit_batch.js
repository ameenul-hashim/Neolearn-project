document.addEventListener("DOMContentLoaded", () => {

    // ======================================================
    // Elements
    // ======================================================


const batchStatus = document.getElementById(
    "batch_status"
);

const publishTypeWrapper = document.getElementById(
    "publishTypeWrapper"
);

const publishDateWrapper = document.getElementById(
    "publishDateWrapper"
);

const publishImmediate = document.getElementById(
    "publish_immediate"
);

const publishScheduled = document.getElementById(
    "publish_scheduled"
);

const admissionCloseWrapper = document.getElementById(
    "admissionCloseWrapper"
);

const courseEndWrapper = document.getElementById(
    "courseEndWrapper"
);

// -------------------------------
// Pricing & Offers
// -------------------------------

const originalPrice = document.getElementById(
    "original_price"
);

const discountType = document.getElementById(
    "discount_type"
);

const discountValue = document.getElementById(
    "discount_value"
);

const discountValueWrapper = document.getElementById(
    "discountValueWrapper"
);

const offerStartWrapper = document.getElementById(
    "offerStartWrapper"
);

const offerEndWrapper = document.getElementById(
    "offerEndWrapper"
);

const discountPrefix = document.getElementById(
    "discountPrefix"
);

const discountHint = document.getElementById(
    "discountHint"
);

// -------------------------------
// Live Marketplace Preview
// -------------------------------

const previewOriginalPrice = document.getElementById(
    "previewOriginalPrice"
);

const previewDiscount = document.getElementById(
    "previewDiscount"
);

const previewFinalPrice = document.getElementById(
    "previewFinalPrice"
);

// -------------------------------
// Thumbnail
// -------------------------------

const thumbnailInput = document.getElementById(
    "batch_thumbnail_input"
);

// -------------------------------
// Marketplace Flow
// -------------------------------

const marketplaceBadges = document.querySelectorAll(
    ".rounded-full"
);

    // ======================================================
    // Publishing Section
    // ======================================================

    function togglePublishing() {

        if (batchStatus.value === "draft") {

            publishTypeWrapper.style.display = "none";

            publishDateWrapper.style.display = "none";

            admissionCloseWrapper.style.display = "none";

            courseEndWrapper.style.display = "none";

            return;

        }

        publishTypeWrapper.style.display = "block";

        admissionCloseWrapper.style.display = "block";

        courseEndWrapper.style.display = "block";

        if (publishScheduled.checked) {

            publishDateWrapper.style.display = "block";

        }

        else {

            publishDateWrapper.style.display = "none";

        }

    }

    // ======================================================
    // Discount Section
    // ======================================================

    function toggleDiscount() {

    const type = discountType.value;

    // -------------------------------
    // No Discount
    // -------------------------------

    if (type === "none") {

        discountValueWrapper.style.display = "none";
        offerStartWrapper.style.display = "none";
        offerEndWrapper.style.display = "none";

        // Clear values
        discountValue.value = "";

        const offerStartInput = document.getElementById("offer_start_date");
        const offerEndInput = document.getElementById("offer_end_date");

        if (offerStartInput) {
            offerStartInput.value = "";
        }

        if (offerEndInput) {
            offerEndInput.value = "";
        }

        calculateFinalPrice();
        return;
    }

    // -------------------------------
    // Show Discount Fields
    // -------------------------------

    discountValueWrapper.style.display = "block";
    offerStartWrapper.style.display = "block";
    offerEndWrapper.style.display = "block";

    // -------------------------------
    // Percentage Discount
    // -------------------------------

    if (type === "percentage") {

        discountPrefix.textContent = "%";

        discountHint.textContent =
            "Enter percentage discount (0 - 100).";

        discountValue.max = "100";

    }

    // -------------------------------
    // Fixed Discount
    // -------------------------------

    else {

        discountPrefix.textContent = "₹";

        discountHint.textContent =
            "Enter fixed amount discount.";

        discountValue.removeAttribute("max");

    }

    calculateFinalPrice();

}

    // ======================================================
    // Live Price Calculator
    // ======================================================

    function calculateFinalPrice() {

    let price = parseFloat(originalPrice.value);

    if (isNaN(price)) {
        price = 0;
    }

    let discount = parseFloat(discountValue.value);

    if (isNaN(discount)) {
        discount = 0;
    }

    let finalPrice = price;

    if (discountType.value === "percentage") {

        finalPrice = price - ((price * discount) / 100);

    }

    else if (discountType.value === "fixed") {

        finalPrice = price - discount;

    }

    if (finalPrice < 0) {

        finalPrice = 0;

    }

    // -----------------------
    // Original Price Preview
    // -----------------------

    if (previewOriginalPrice) {

        previewOriginalPrice.textContent =
            "₹" + price.toFixed(2);

    }

    // -----------------------
    // Discount Preview
    // -----------------------

    if (previewDiscount) {

        if (discountType.value === "none") {

            previewDiscount.textContent = "None";

        }

        else if (discountType.value === "percentage") {

            previewDiscount.textContent =
                discount + "%";

        }

        else {

            previewDiscount.textContent =
                "₹" + discount.toFixed(2);

        }

    }

    // -----------------------
    // Final Price Preview
    // -----------------------

    if (previewFinalPrice) {

        previewFinalPrice.textContent =
            "₹" + finalPrice.toFixed(2);

    }

}
    // ======================================================
    // Marketplace Status Preview
    // ======================================================

    function updateMarketplacePreview() {

    if (!marketplaceBadges.length) {
        return;
    }

    // Reset all badges
    marketplaceBadges.forEach((badge) => {
        badge.style.opacity = "0.35";
    });

    // Draft
    if (batchStatus.value === "draft") {

        if (marketplaceBadges[0]) {
            marketplaceBadges[0].style.opacity = "1";
        }

        return;
    }

    // Scheduled Publish
    if (publishScheduled && publishScheduled.checked) {

        if (marketplaceBadges[1]) {
            marketplaceBadges[1].style.opacity = "1";
        }

        return;
    }

    // Immediate Publish
    if (marketplaceBadges[2]) {
        marketplaceBadges[2].style.opacity = "1";
    }

}

    // ======================================================
    // Thumbnail Preview
    // ======================================================
// ======================================================
// Thumbnail Preview
// ======================================================

function previewThumbnail() {

    const preview = document.getElementById(
        "thumbnailPreview"
    );

    const fileName = document.getElementById(
        "thumbnailFileName"
    );

    if (!preview || !thumbnailInput) {
        return;
    }

    const file = thumbnailInput.files[0];

    // User didn't select a new image
    if (!file) {

        if (fileName) {
            fileName.textContent = "Current image";
        }

        return;
    }

    // Show selected filename
    if (fileName) {
        fileName.textContent = file.name;
    }

    const reader = new FileReader();

    reader.onload = function (e) {

        preview.src = e.target.result;

        preview.classList.remove("hidden");

    };

    reader.readAsDataURL(file);

}

    // ======================================================
    // Events
    // ======================================================

    if (batchStatus) {

    batchStatus.addEventListener("change", () => {

        togglePublishing();

        updateMarketplacePreview();

    });

}

if (publishImmediate) {

    publishImmediate.addEventListener("change", () => {

        togglePublishing();

        updateMarketplacePreview();

    });

}

if (publishScheduled) {

    publishScheduled.addEventListener("change", () => {

        togglePublishing();

        updateMarketplacePreview();

    });

}

if (discountType) {

    discountType.addEventListener("change", toggleDiscount);

}

if (originalPrice) {

    originalPrice.addEventListener("input", calculateFinalPrice);

}

if (discountValue) {

    discountValue.addEventListener("input", calculateFinalPrice);

}

    if (thumbnailInput) {

        thumbnailInput.addEventListener(
            "change",
            previewThumbnail
        );

    }

    // ======================================================
    // Initialize
    // ======================================================

    togglePublishing();

    toggleDiscount();

    calculateFinalPrice();

    updateMarketplacePreview();

});