window.addEventListener("DOMContentLoaded", () => {

    const toggleButtons = document.querySelectorAll(
        ".toggle-password"
    )

    toggleButtons.forEach((button) => {

        button.addEventListener("click", () => {

            const targetId = button.getAttribute(
                "data-target"
            )

            const input = document.getElementById(
                targetId
            )

            if(input.type === "password"){

                input.type = "text"

                button.innerText = "✖"

            }

            else{

                input.type = "password"

                button.innerText = "👁"

            }

        })

    })

})