window.addEventListener("DOMContentLoaded", () => {

    const otpInputs = document.querySelectorAll(".otp-box")

    const finalOtp = document.getElementById("final-otp")

    otpInputs.forEach((input, index) => {

        input.addEventListener("input", function () {

            this.value = this.value.replace(/[^0-9]/g,'')

            if(this.value.length === 1){

                if(index < otpInputs.length - 1){

                    otpInputs[index + 1].focus()

                }

            }

            combineOtp()

        })

        input.addEventListener("keydown", function (e) {

            if(
                e.key === "Backspace" &&
                this.value === "" &&
                index > 0
            ){

                otpInputs[index - 1].focus()

            }

        })

    })

    function combineOtp(){

        let otp = ""

        otpInputs.forEach((input) => {

            otp += input.value

        })

        finalOtp.value = otp

    }

    // TIMER

    const timer = document.getElementById("timer")

    const resendLink = document.getElementById("resend-link")

    const timerWrapper = document.getElementById("timer-wrapper")

    resendLink.style.display = "none"

    let seconds = 59

    const interval = setInterval(() => {

        seconds--

        let formatted = seconds < 10
            ? `00:0${seconds}`
            : `00:${seconds}`

        timer.innerText = formatted

        if(seconds <= 0){

            clearInterval(interval)

            timerWrapper.style.display = "none"

            resendLink.style.display = "inline-block"

        }

    },1000)

})