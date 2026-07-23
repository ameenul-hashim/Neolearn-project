document.addEventListener("DOMContentLoaded", function () {

    const modal = document.getElementById("teacherBlockModal");

    const teacherNameBox = document.getElementById("modalTeacherName");

    const confirmInput = document.getElementById("confirmTeacherInput");

    const confirmButton = document.getElementById("confirmTeacherBtn");

    const cancelButton = document.getElementById("cancelTeacherBtn");

    const form = document.getElementById("teacherBlockForm");

    const modalTitle = document.getElementById("teacherModalTitle");

    const modalMessage = document.getElementById("teacherModalMessage");

    let currentTeacher = "";

    if (
        !modal ||
        !teacherNameBox ||
        !confirmInput ||
        !confirmButton ||
        !cancelButton ||
        !form
    ) {
        return;
    }

    document.querySelectorAll(".teacher-block-btn").forEach(function (button) {

        button.addEventListener("click", function () {

            const teacherId = this.dataset.id;

            const teacherName = this.dataset.name;

            const action = this.dataset.action;

            currentTeacher = teacherName;

            teacherNameBox.textContent = teacherName;

            confirmInput.value = "";

            confirmButton.disabled = true;

            confirmButton.classList.add("opacity-50");

            confirmButton.classList.remove("opacity-100");

            if (action === "block") {

                modalTitle.textContent = "Block Teacher";

                modalMessage.innerHTML = `
                    Blocking this teacher will prevent login.<br><br>
                    Batch assignments and subject assignments remain safe.
                `;

                confirmButton.textContent = "Block Teacher";

                confirmButton.classList.remove("bg-green-600");

                confirmButton.classList.add("bg-orange-600");

                form.action = `/admin-panel/teachers/${teacherId}/block/`;

            } else {

                modalTitle.textContent = "Unblock Teacher";

                modalMessage.innerHTML = `
                    This teacher will be able to login again.
                `;

                confirmButton.textContent = "Unblock Teacher";

                confirmButton.classList.remove("bg-orange-600");

                confirmButton.classList.add("bg-green-600");

                form.action = `/admin-panel/teachers/${teacherId}/unblock/`;

            }

            modal.classList.remove("hidden");

            modal.classList.add("flex");

        });

    });

    function closeModal() {

        modal.classList.remove("flex");

        modal.classList.add("hidden");

        confirmInput.value = "";

        confirmButton.disabled = true;

    }

    cancelButton.addEventListener("click", closeModal);

    modal.addEventListener("click", function (e) {

        if (e.target === modal) {

            closeModal();

        }

    });

    document.addEventListener("keydown", function (e) {

        if (e.key === "Escape") {

            closeModal();

        }

    });

    confirmInput.addEventListener("input", function () {

        if (this.value.trim() === currentTeacher) {

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