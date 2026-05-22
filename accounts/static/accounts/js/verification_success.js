window.addEventListener("DOMContentLoaded",()=>{

    /* TIMER */

    let seconds=4;

    const timer=document.getElementById(
        "redirect-timer"
    );

    const loaderBar=document.getElementById(
        "loader-bar"
    );

    /* LOADER ANIMATION */

    if(loaderBar){

        loaderBar.style.transition=
        "width 4s linear";

        setTimeout(()=>{

            loaderBar.style.width="100%";

        },100);

    }

    /* COUNTDOWN */

    const countdown=setInterval(()=>{

        seconds--;

        if(timer){

            timer.innerText=seconds;

        }

        if(seconds <= 0){

            clearInterval(countdown);

        }

    },1000);

});