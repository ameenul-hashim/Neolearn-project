const editButton=document.getElementById(
    'editImageButton'
)

const fileInput=document.getElementById(
    'profileImageInput'
)

const cropModal=document.getElementById(
    'cropModal'
)

const cropImage=document.getElementById(
    'cropImage'
)

const saveCrop=document.getElementById(
    'saveCrop'
)

const cancelCrop=document.getElementById(
    'cancelCrop'
)

let cropper


// OPEN FILE INPUT

if(editButton){

    editButton.addEventListener(
        'click',
        ()=>{

            fileInput.click()

        }
    )
}


// IMAGE SELECT

if(fileInput){

    fileInput.addEventListener(
        'change',
        (e)=>{

            const file=e.target.files[0]

            if(file){

                const reader=new FileReader()

                reader.onload=(event)=>{

                    cropImage.src=event.target.result

                    cropModal.classList.remove(
                        'hidden'
                    )

                    cropModal.classList.add(
                        'flex'
                    )

                    if(cropper){

                        cropper.destroy()
                    }

                    cropper=new Cropper(
                        cropImage,
                        {

                            aspectRatio:1,

                            viewMode:2,

                            dragMode:'move',

                            autoCropArea:1,

                            responsive:true,

                            background:false,

                            guides:true,

                            center:true,

                            highlight:true,

                            cropBoxMovable:true,

                            cropBoxResizable:false,

                            toggleDragModeOnDblclick:false,

                            movable:true,

                            zoomable:true,

                            scalable:false,

                            rotatable:false,

                            minContainerWidth:450,

                            minContainerHeight:450,

                        }
                    )
                }

                reader.readAsDataURL(file)
            }
        }
    )
}


// CANCEL CROP

if(cancelCrop){

    cancelCrop.addEventListener(
        'click',
        ()=>{

            cropModal.classList.add(
                'hidden'
            )

            cropModal.classList.remove(
                'flex'
            )

            if(cropper){

                cropper.destroy()
            }

        }
    )
}


// SAVE CROPPED IMAGE

if(saveCrop){

    saveCrop.addEventListener(
        'click',
        ()=>{

            const canvas=cropper.getCroppedCanvas(
                {
                    width:600,
                    height:600,

                    imageSmoothingEnabled:true,

                    imageSmoothingQuality:'high',
                }
            )

            canvas.toBlob(
                (blob)=>{

                    const formData=new FormData()

                    formData.append(
                        'profile_image',
                        blob,
                        'profile.png'
                    )

                    formData.append(
                        'csrfmiddlewaretoken',
                        document.querySelector(
                            '[name=csrfmiddlewaretoken]'
                        ).value
                    )

                    fetch(
                        '/students/update-profile-image/',
                        {
                            method:'POST',
                            body:formData
                        }
                    )

                    .then(response=>response.text())

                    .then(()=>{

                        window.location.reload()

                    })

                },
                'image/jpeg',
                0.95
            )
        }
    )
}