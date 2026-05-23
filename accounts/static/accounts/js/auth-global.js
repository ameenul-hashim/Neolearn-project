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

const togglePassword=document.getElementById(
    "togglePassword"
);

const password=document.getElementById(
    "password"
);

if(togglePassword && password){

    const eyeOpen=`

    <svg
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke-width="1.8"
        stroke="currentColor"
        class="w-[18px] h-[18px]"
    >

        <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.964-7.178z"
        />

        <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
        />

    </svg>

    `;

    const eyeClosed=`

    <svg
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke-width="1.8"
        stroke="currentColor"
        class="w-[18px] h-[18px]"
    >

        <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M3 3l18 18"
        />

        <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M10.477 10.469a3 3 0 004.243 4.243"
        />

        <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M9.88 5.09A9.953 9.953 0 0112 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639a10.01 10.01 0 01-4.043 5.135M6.228 6.228A9.956 9.956 0 002.037 11.68a1.012 1.012 0 000 .639 10.01 10.01 0 003.483 4.593"
        />

    </svg>

    `;

    togglePassword.addEventListener("click",()=>{

        if(password.type==="password"){

            password.type="text";

            togglePassword.innerHTML=eyeClosed;

        }

        else{

            password.type="password";

            togglePassword.innerHTML=eyeOpen;

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

    const eyeOpen=`

    <svg
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke-width="1.8"
        stroke="currentColor"
        class="w-[18px] h-[18px]"
    >

        <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.964-7.178z"
        />

        <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
        />

    </svg>

    `;

    const eyeClosed=`

    <svg
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke-width="1.8"
        stroke="currentColor"
        class="w-[18px] h-[18px]"
    >

        <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M3 3l18 18"
        />

        <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M10.477 10.469a3 3 0 004.243 4.243"
        />

        <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M9.88 5.09A9.953 9.953 0 0112 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639a10.01 10.01 0 01-4.043 5.135M6.228 6.228A9.956 9.956 0 002.037 11.68a1.012 1.012 0 000 .639 10.01 10.01 0 003.483 4.593"
        />

    </svg>

    `;

    toggleConfirmPassword.addEventListener("click",()=>{

        if(confirmPassword.type==="password"){

            confirmPassword.type="text";

            toggleConfirmPassword.innerHTML=eyeClosed;

        }

        else{

            confirmPassword.type="password";

            toggleConfirmPassword.innerHTML=eyeOpen;

        }

    });

}

// resubmission prevention
    if (window.history.replaceState) {

        window.history.replaceState(
            null,
            null,
            window.location.href
        );
    }



