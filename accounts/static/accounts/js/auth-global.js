// AUTO HIDE ALERTS

// AUTO HIDE ALERTS

const alerts=document.querySelectorAll(
    ".message-box, .success-box, .error-box"
);

alerts.forEach((alert)=>{

    setTimeout(()=>{

        alert.style.transition="0.5s ease";

        alert.style.opacity="0";

        alert.style.transform="translateY(-10px)";

        setTimeout(()=>{

            alert.remove();

        },500);

    },5000);

});


// PASSWORD TOGGLE

const togglePassword=document.getElementById("togglePassword");

const password=document.getElementById("password");

if(togglePassword && password){

    togglePassword.addEventListener("click",()=>{

        if(password.type==="password"){

            password.type="text";

            togglePassword.innerHTML="✖";

        }

        else{

            password.type="password";

            togglePassword.innerHTML="👁";

        }

    });

}


// CONFIRM PASSWORD TOGGLE

const toggleConfirmPassword=document.getElementById(
    "toggleConfirmPassword"
);

const confirmPassword=document.getElementById(
    "confirmPassword"
);

if(toggleConfirmPassword && confirmPassword){

    toggleConfirmPassword.addEventListener("click",()=>{

        if(confirmPassword.type==="password"){

            confirmPassword.type="text";

            toggleConfirmPassword.innerHTML="✖";

        }

        else{

            confirmPassword.type="password";

            toggleConfirmPassword.innerHTML="👁";

        }

    });

}