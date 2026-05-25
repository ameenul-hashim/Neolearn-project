from django.shortcuts import render,redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
from django.contrib import messages
import cloudinary.uploader

from .models import StudentProfile


@login_required(login_url='signin')
@cache_control(no_cache=True,must_revalidate=True,no_store=True)

def dashboard_view(request):

    if request.user.is_staff or request.user.is_superuser:

        messages.error(
            request,
            'Admin login is not allowed here. Please use the admin login area.'
        )

        return redirect('signin')

    return render(
        request,
        'students/dashboard.html'
    )



# PROFILE PAGE

@login_required(login_url='signin')
@cache_control(no_cache=True,must_revalidate=True,no_store=True)

def profile_view(request):

    profile,created=StudentProfile.objects.get_or_create(
        user=request.user
    )

    return render(
        request,
        'students/profile.html',
        {
            'profile':profile
        }
    )


# PROFILE IMAGE UPDATE

@login_required(login_url='signin')
@cache_control(no_cache=True,must_revalidate=True,no_store=True)

def update_profile_image_view(request):

    if request.method=='POST':

        image=request.FILES.get('profile_image')


        # IMAGE SIZE VALIDATION

        if image and image.size > 10 * 1024 * 1024:

            messages.error(
                request,
                'Image size must be below 10MB.'
            )

            return redirect('profile')


        if image:

            profile,created=StudentProfile.objects.get_or_create(
                user=request.user
            )


            # DELETE OLD IMAGE FROM CLOUDINARY

            if profile.cloudinary_public_id:

                try:

                    cloudinary.uploader.destroy(
                        profile.cloudinary_public_id
                    )

                except:

                    pass


            # UPLOAD NEW IMAGE

            uploaded_image=cloudinary.uploader.upload(
                image,
                folder='neolearn_profiles'
            )


            # SAVE NEW IMAGE

            profile.profile_image=uploaded_image[
                'secure_url'
            ]

            profile.cloudinary_public_id=uploaded_image[
                'public_id'
            ]

            profile.save()


            messages.success(
                request,
                'Profile image updated successfully.'
            )

        else:

            messages.error(
                request,
                'Please select an image.'
            )

    return redirect('profile')