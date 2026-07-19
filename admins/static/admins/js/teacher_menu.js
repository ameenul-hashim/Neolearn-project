document.addEventListener("DOMContentLoaded", function () {

    const buttons = document.querySelectorAll(".teacher-menu-btn");

    buttons.forEach(function (button) {

        button.addEventListener("click", function (e) {

            e.stopPropagation();

            const menu = this.nextElementSibling;

            document.querySelectorAll(".teacher-menu").forEach(function (item) {

                if (item !== menu) {

                    item.classList.add("invisible");
                    item.classList.add("opacity-0");

                }

            });

            if (menu.classList.contains("invisible")) {

                menu.classList.remove("invisible");
                menu.classList.remove("opacity-0");

            } else {

                menu.classList.add("invisible");
                menu.classList.add("opacity-0");

            }

        });

    });

    document.addEventListener("click", function () {

        document.querySelectorAll(".teacher-menu").forEach(function (menu) {

            menu.classList.add("invisible");
            menu.classList.add("opacity-0");

        });

    });

});