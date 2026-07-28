/* ==========================================================
   NeoLearn Shared Toast Notifications
   Used By:
   - Student Dashboard
   - Admin Dashboard
   - Teacher Dashboard
========================================================== */

document.addEventListener("DOMContentLoaded", function () {

    const messageContainer = document.getElementById("messageContainer");

    if (!messageContainer) return;

    const messages = messageContainer.querySelectorAll(".message-item");

    messages.forEach(function (message) {

        const closeBtn = message.querySelector(".message-close");

        let removed = false;

        function removeMessage() {

            if (removed) return;

            removed = true;

            message.classList.add("hide");

            setTimeout(function () {

                if (message.parentNode) {
                    message.parentNode.removeChild(message);
                }

            }, 350);

        }

        // Auto Remove
        const timer = setTimeout(removeMessage, 5000);

        // Manual Close
        if (closeBtn) {

            closeBtn.addEventListener("click", function (e) {

                e.preventDefault();

                e.stopPropagation();

                clearTimeout(timer);

                removeMessage();

            });

        }

    });

});