window.addEventListener("DOMContentLoaded", () => {

    /* OTP INPUTS */

    const otpInputs = document.querySelectorAll(".otp-box")

    const finalOtp = document.getElementById("final-otp")



    /* UPDATE OTP */

    function updateOtp() {

        let otp = ""

        otpInputs.forEach((input) => {

            otp += input.value

        })

        finalOtp.value = otp

    }



    /* OTP EVENTS */

    otpInputs.forEach((input, index) => {

        /* INPUT EVENT */

        input.addEventListener("input", () => {

            /* ONLY NUMBERS */

            input.value = input.value.replace(/\D/g, "")

            /* AUTO NEXT FIELD */

            if (

                input.value &&

                index < otpInputs.length - 1

            ) {

                otpInputs[index + 1].focus()

            }

            /* UPDATE OTP */

            updateOtp()

        })



        /* BACKSPACE EVENT */

        input.addEventListener("keydown", (e) => {

            if (

                e.key === "Backspace" &&

                !input.value &&

                index > 0

            ) {

                otpInputs[index - 1].focus()

            }

        })

    })



    /* TIMER */

    const timer = document.getElementById("timer")

    const resendLink = document.getElementById("resend-link")

    const timerWrapper = document.getElementById("timer-wrapper")



    if (

        timer &&

        resendLink &&

        timerWrapper

    ) {

        resendLink.style.display = "none"

        let seconds = 59

        timer.textContent = seconds

        const interval = setInterval(() => {

            seconds--

            timer.textContent = seconds

            if (seconds <= 0) {

                clearInterval(interval)

                timerWrapper.style.display = "none"

                resendLink.style.display = "inline-block"

            }

        }, 1000)

    }



    /* AUTO HIDE ALERTS */

    setTimeout(() => {

        document.querySelectorAll(

            ".message-box, .success-box, .error-box"

        ).forEach((msg) => {

            msg.style.transition = "0.4s"

            msg.style.opacity = "0"

            msg.style.transform = "translateY(-10px)"

            setTimeout(() => {

                msg.remove()

            }, 400)

        })

    }, 3000)

})
