function togglePassword(inputId,eyeId){

    const input=document.getElementById(inputId)

    const eye=document.getElementById(eyeId)

    if(input.type==="password"){

        input.type="text"

        eye.innerHTML="✖"

    }

    else{

        input.type="password"

        eye.innerHTML="👁"

    }

}

/* AUTO HIDE MESSAGE */

setTimeout(()=>{

    const messages=document.querySelectorAll('.auto-hide')

    messages.forEach(message=>{

        message.style.transition='0.5s'

        message.style.opacity='0'

        setTimeout(()=>{

            message.remove()

        },500)

    })

},5000)