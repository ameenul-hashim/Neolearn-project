window.addEventListener("DOMContentLoaded", () => {

    /* ========================= */
    /* OTP BOXES */
    /* ========================= */

    const otpInputs = document.querySelectorAll(".otp-box")

    const finalOtp = document.getElementById("final-otp")

    otpInputs.forEach((input, index) => {

        /* ONLY NUMBER */

        input.addEventListener("input", function () {

            this.value = this.value.replace(/[^0-9]/g, '')

            /* AUTO NEXT */

            if (this.value.length === 1) {

                if (index < otpInputs.length - 1) {

                    otpInputs[index + 1].focus()

                }

            }

            combineOtp()

        })

        /* BACKSPACE */

        input.addEventListener("keydown", function (e) {

            if (e.key === "Backspace" && this.value === "") {

                if (index > 0) {

                    otpInputs[index - 1].focus()

                }

            }

        })

    })

    /* ========================= */
    /* COMBINE OTP */
    /* ========================= */

    function combineOtp() {

        let otp = ""

        otpInputs.forEach((input) => {

            otp += input.value

        })

        finalOtp.value = otp

    }

    /* ========================= */
    /* REAL LIVE TIMER */
    /* ========================= */

    const timer = document.getElementById("timer")

    const resendLink = document.getElementById("resend-link")

    const timerWrapper = document.getElementById("timer-wrapper")

    /* HIDE RESEND INITIALLY */

    resendLink.style.display = "none"

    /* START FROM 59 */

    let seconds = 59

    /* INITIAL DISPLAY */

    timer.textContent = seconds

    /* REAL RUNNING TIMER */

    const timerInterval = setInterval(() => {

        seconds--

        /* UPDATE LIVE */

        timer.textContent = seconds

        /* AFTER 0 */

        if (seconds <= 0) {

            clearInterval(timerInterval)

            /* HIDE TIMER */

            timerWrapper.style.display = "none"

            /* SHOW RESEND */

            resendLink.style.display = "inline-block"

        }

    }, 1000)

    /* ========================= */
    /* AUTO HIDE MESSAGE */
    /* ========================= */

    setTimeout(() => {

        const messages = document.querySelectorAll(".auto-hide")

        messages.forEach((message) => {

            message.style.transition = "0.5s"

            message.style.opacity = "0"

            setTimeout(() => {

                message.remove()

            }, 500)

        })

    }, 5000)

})