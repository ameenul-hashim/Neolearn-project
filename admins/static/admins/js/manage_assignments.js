document.addEventListener("DOMContentLoaded", function () {

    // ===========================================
    // ELEMENTS
    // ===========================================

    const modal = document.getElementById("removeBatchModal");
    const batchNameBox = document.getElementById("modalBatchName");
    const batchNameInline = document.getElementById("modalBatchNameInline");

    const confirmInput = document.getElementById("confirmBatchInput");
    const confirmButton = document.getElementById("confirmRemoveBtn");
    const cancelButton = document.getElementById("cancelRemoveBatch");
    const removeForm = document.getElementById("removeBatchForm");

    if (
        !modal ||
        !batchNameBox ||
        !confirmInput ||
        !confirmButton ||
        !cancelButton ||
        !removeForm
    ) {
        return;
    }

    let currentBatchName = "";

    // ===========================================
    // OPEN MODAL
    // ===========================================

    document.querySelectorAll(".remove-access-btn").forEach(function (button) {

        button.addEventListener("click", function () {

            currentBatchName = this.dataset.batch;
            const assignmentId = this.dataset.id;

            batchNameBox.textContent = currentBatchName;

            if (batchNameInline) {
                batchNameInline.textContent = currentBatchName;
            }

            confirmInput.value = "";

            confirmButton.disabled = true;

            confirmButton.classList.add("opacity-50");
            confirmButton.classList.remove("opacity-100");

            // Correct URL
            removeForm.action =
    `/admin-panel/teacher-batch/${assignmentId}/remove/`;

            modal.classList.remove("hidden");
            modal.classList.add("flex");

        });

    });

    // ===========================================
    // CLOSE MODAL
    // ===========================================

    function closeModal() {

        modal.classList.remove("flex");
        modal.classList.add("hidden");

        confirmInput.value = "";

        confirmButton.disabled = true;

        confirmButton.classList.add("opacity-50");
        confirmButton.classList.remove("opacity-100");

    }

    cancelButton.addEventListener("click", closeModal);

    modal.addEventListener("click", function (event) {

        if (event.target === modal) {
            closeModal();
        }

    });

    document.addEventListener("keydown", function (event) {

        if (event.key === "Escape" && modal.classList.contains("flex")) {
            closeModal();
        }

    });

    // ===========================================
    // CONFIRM BATCH NAME
    // ===========================================

    confirmInput.addEventListener("input", function () {

        if (this.value.trim() === currentBatchName) {

            confirmButton.disabled = false;

            confirmButton.classList.remove("opacity-50");
            confirmButton.classList.add("opacity-100");

        } else {

            confirmButton.disabled = true;

            confirmButton.classList.add("opacity-50");
            confirmButton.classList.remove("opacity-100");

        }

    });

});