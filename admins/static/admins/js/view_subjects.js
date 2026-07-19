document.addEventListener("DOMContentLoaded", function () {

    const modal = document.getElementById("removeSubjectModal");

    const subjectNameBox = document.getElementById("modalSubjectName");

    const confirmInput = document.getElementById("confirmSubjectInput");

    const confirmButton = document.getElementById("confirmRemoveSubjectBtn");

    const cancelButton = document.getElementById("cancelRemoveSubject");

    const removeForm = document.getElementById("removeSubjectForm");

    let currentSubjectName = "";

    // ===========================================
    // OPEN REMOVE SUBJECT MODAL
    // ===========================================

    document.querySelectorAll(".remove-subject-btn").forEach(function (button) {

        button.addEventListener("click", function () {

            currentSubjectName = this.dataset.subject;

            const assignmentId = this.dataset.id;

            subjectNameBox.textContent = currentSubjectName;

            confirmInput.value = "";

            confirmButton.disabled = true;

            confirmButton.classList.add("opacity-50");

            confirmButton.classList.remove("opacity-100");

            removeForm.action = `/admin-panel/teacher-subject/${assignmentId}/remove/`;

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

    // ===========================================
    // ENABLE REMOVE BUTTON
    // ===========================================

    confirmInput.addEventListener("input", function () {

        if (this.value.trim() === currentSubjectName) {

            confirmButton.disabled = false;

            confirmButton.classList.remove("opacity-50");

            confirmButton.classList.add("opacity-100");

        }

        else {

            confirmButton.disabled = true;

            confirmButton.classList.add("opacity-50");

            confirmButton.classList.remove("opacity-100");

        }

    });

    // ===========================================
    // ESC KEY CLOSE
    // ===========================================

    document.addEventListener("keydown", function (event) {

        if (event.key === "Escape") {

            closeModal();

        }

    });

});