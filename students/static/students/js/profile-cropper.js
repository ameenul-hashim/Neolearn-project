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


if(editButton){

    editButton.addEventListener(
        'click',
        ()=>{

            fileInput.click()

        }
    )
}


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
                            viewMode:1,
                            dragMode:'move',
                            autoCropArea:1,
                            responsive:true,
                            background:false,
                        }
                    )
                }

                reader.readAsDataURL(file)
            }
        }
    )
}


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

            cropper.destroy()
        }
    )
}


if(saveCrop){

    saveCrop.addEventListener(
        'click',
        ()=>{

            const canvas=cropper.getCroppedCanvas(
                {
                    width:500,
                    height:500
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

                }
            )
        }
    )
}