document.addEventListener("DOMContentLoaded", () => {

    // ======================================================
    // Elements
    // ======================================================

    const batchStatus = document.getElementById("batch_status");

    const publishTypeWrapper = document.getElementById("publishTypeWrapper");

    const publishDateWrapper = document.getElementById("publishDateWrapper");

    const publishImmediate = document.getElementById("publish_immediate");

    const publishScheduled = document.getElementById("publish_scheduled");

    const admissionCloseWrapper = document.getElementById("admissionCloseWrapper");

    const courseEndWrapper = document.getElementById("courseEndWrapper");

    const discountType = document.getElementById("discount_type");

    const discountValueWrapper = document.getElementById("discountValueWrapper");

    const offerStartWrapper = document.getElementById("offerStartWrapper");

    const offerEndWrapper = document.getElementById("offerEndWrapper");

    const discountPrefix = document.getElementById("discountPrefix");

    const discountHint = document.getElementById("discountHint");

    const originalPrice = document.querySelector(
        'input[name="original_price"]'
    );

    const discountValue = document.getElementById("discount_value");

    const finalPriceElement = document.querySelector(
        ".text-cyan-400"
    );

    const discountPreview = document.querySelector(
        ".text-emerald-400"
    );

    const originalPricePreview = document.querySelector(
        ".flex.justify-between .text-white"
    );

    const thumbnailInput = document.querySelector(
        'input[name="batch_thumbnail"]'
    );

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

        if (discountType.value === "none") {

            discountValueWrapper.style.display = "none";

            offerStartWrapper.style.display = "none";

            offerEndWrapper.style.display = "none";

            calculateFinalPrice();

            return;

        }

        discountValueWrapper.style.display = "block";

        offerStartWrapper.style.display = "block";

        offerEndWrapper.style.display = "block";

        if (discountType.value === "percentage") {

            discountPrefix.innerHTML = "%";

            discountHint.innerHTML =
                "Enter percentage discount (0 - 100).";

        }

        else {

            discountPrefix.innerHTML = "₹";

            discountHint.innerHTML =
                "Enter fixed amount discount.";

        }

        calculateFinalPrice();

    }

    // ======================================================
    // Live Price Calculator
    // ======================================================

    function calculateFinalPrice() {

        let price = parseFloat(originalPrice.value);

        if (isNaN(price))
            price = 0;

        let discount = parseFloat(discountValue.value);

        if (isNaN(discount))
            discount = 0;

        let finalPrice = price;

        if (discountType.value === "percentage") {

            finalPrice = price - ((price * discount) / 100);

        }

        if (discountType.value === "fixed") {

            finalPrice = price - discount;

        }

        if (finalPrice < 0) {

            finalPrice = 0;

        }

        if (originalPricePreview) {

            originalPricePreview.innerHTML =
                "₹" + price.toFixed(2);

        }

        if (discountPreview) {

            if (discountType.value === "none") {

                discountPreview.innerHTML = "None";

            }

            else if (discountType.value === "percentage") {

                discountPreview.innerHTML =
                    discount + "%";

            }

            else {

                discountPreview.innerHTML =
                    "₹" + discount.toFixed(2);

            }

        }

        if (finalPriceElement) {

            finalPriceElement.innerHTML =
                "₹" + finalPrice.toFixed(2);

        }

    }

    // ======================================================
    // Marketplace Status Preview
    // ======================================================

    function updateMarketplacePreview() {

        marketplaceBadges.forEach(badge => {

            badge.style.opacity = ".35";

        });

        if (batchStatus.value === "draft") {

            marketplaceBadges[0].style.opacity = "1";

            return;

        }

        if (publishScheduled.checked) {

            marketplaceBadges[1].style.opacity = "1";

        }

        else {

            marketplaceBadges[2].style.opacity = "1";

        }

    }

    // ======================================================
    // Thumbnail Preview
    // ======================================================

    function previewThumbnail() {

    const preview = document.getElementById("thumbnailPreview");

    const fileName = document.getElementById("thumbnailFileName");

    if (!preview || !thumbnailInput)
        return;

    const file = thumbnailInput.files[0];

    if (!file) {

        preview.src = "";

        preview.classList.add("hidden");

        if (fileName) {

            fileName.textContent = "No image selected";

        }

        return;

    }

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