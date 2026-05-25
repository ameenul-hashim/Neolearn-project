const sidebar=document.getElementById('sidebar')

const openSidebar=document.getElementById('openSidebar')

const closeSidebar=document.getElementById('closeSidebar')

const overlay=document.getElementById('overlay')


openSidebar.addEventListener(
    'click',
    ()=>{

        sidebar.classList.remove(
            '-translate-x-full'
        )

        overlay.classList.remove(
            'hidden'
        )

    }
)


closeSidebar.addEventListener(
    'click',
    ()=>{

        sidebar.classList.add(
            '-translate-x-full'
        )

        overlay.classList.add(
            'hidden'
        )

    }
)


overlay.addEventListener(
    'click',
    ()=>{

        sidebar.classList.add(
            '-translate-x-full'
        )

        overlay.classList.add(
            'hidden'
        )

    }
)