from django.shortcuts import render, redirect
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from .decorators import admin_required
from decimal import Decimal, InvalidOperation
from .models import Batch
from django.shortcuts import get_object_or_404

@cache_control(no_cache=True,must_revalidate=True,no_store=True)
def admin_signin_view(request):

    # IF ALREADY LOGGED IN
    if request.user.is_authenticated:
        if (request.user.is_staff or request.user.is_superuser):
            return redirect('admin_dashboard')

    # POST METHOD

    if request.method == 'POST':
        email=request.POST.get('email')
        password=request.POST.get('password')

        # EMPTY FIELD CHECK
        if not email or not password:
            messages.error(request,'All fields are required.')
            return redirect('admin_signin')

        # EMAIL FORMAT CHECK
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request,'Enter a valid email address.')
            return redirect('admin_signin')

        # USER EXIST CHECK
        try:
            existing_user=User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request,'Admin account not found.')
            return redirect('admin_signin')

        # AUTHENTICATION
        user=authenticate(request,username=existing_user.username,password=password)

        # PASSWORD ERROR
        if user is None:
            messages.error(request,'Incorrect password.')
            return redirect('admin_signin')

        # STAFF / SUPERUSER CHECK
        if (not user.is_staff and  not user.is_superuser):
            messages.error(request,('Access denied. ''Admin login only.'))
            return redirect('admin_signin')

        # LOGIN
        login(request,user)
        messages.success(request,'Admin login successful.')
        return redirect('admin_dashboard')
    return render(request, "admins/admin_signin.html")


@cache_control(no_cache=True,must_revalidate=True,no_store=True)
@admin_required
def admin_dashboard_view(request):

    # BLOCK NORMAL USERS
    if (not request.user.is_staff and not request.user.is_superuser):
        messages.error(request,'Access denied.')
        return redirect('admin_signin')

    response = render(request, 'admins/dashboard/dashboard.html')

    response['Cache-Control']=('no-cache, no-store, must-revalidate')

    response['Pragma']='no-cache'

    response['Expires']='0'

    return response


@login_required(login_url='admin_signin')
def admin_logout_view(request):

    logout(request)

    request.session.flush()

    response = redirect('admin_signin')

    response.delete_cookie('sessionid')

    response.delete_cookie('csrftoken')

    messages.success(request,'Logged out successfully.')

    return response      


@cache_control(no_cache=True,must_revalidate=True,no_store=True)
@admin_required
def admin_students_view(request):

    # ADMIN CHECK
    if (not request.user.is_staff and not request.user.is_superuser):
        messages.error(request,'Access denied.')
        return redirect('admin_signin')
    # SEARCH

    search=request.GET.get('search','')

    # FILTER

    status=request.GET.get('status','all')

    # SORT

    sort=request.GET.get('sort','newest')

    students=User.objects.filter(is_staff=False,is_superuser=False)

    # SEARCH FILTER

    if search:
        students=students.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search))

    # ACTIVE / INACTIVE

    if status=='active':
        students=students.filter(is_active=True)
    elif status=='inactive':
        students=students.filter(is_active=False)

    # SORTING

    if sort=='oldest':
        students=students.order_by('date_joined')
    elif sort=='a-z':
        students=students.order_by('username')
    elif sort=='z-a':
        students=students.order_by('-username')
    else:
        students=students.order_by('-date_joined')

    # PAGINATION

    paginator=Paginator(students,10)
    page_number=request.GET.get('page')
    page_obj=paginator.get_page(page_number)
    context={
        'page_obj':page_obj,
        'search':search,
        'status':status,
        'sort':sort,
    }

    return render(request, 'admins/students/students.html', context)



@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def block_student_view(request,user_id):
    user=User.objects.get(id=user_id)
    if request.method=='POST':
        user.is_active=False
        user.save()
        messages.success(request,'Student blocked successfully.')
        return redirect('admin_students')
    return render(request,'admins/students/block_student.html',{'student': user})



@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def unblock_student_view(request,user_id):
    user=User.objects.get(id=user_id)
    if request.method=='POST':
        user.is_active=True
        user.save()
        messages.success(request,'Student unblocked successfully.')
        return redirect('admin_students')

    return render(request,'admins/students/unblock_student.html',{'student': user})



@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def delete_student_view(request,user_id):
    user=User.objects.get(id=user_id)
    if request.method=='POST':
        user.delete()
        messages.success(request,'Student deleted successfully.')
        return redirect('admin_students')

    return render(request,'admins/students/delete_student.html',{'student': user})



@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def admin_batches_view(request):

    batches = Batch.objects.all()
    context = {'batches': batches,}
    return render(request,"admins/batches/batches.html",context)
    


@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def create_batch_view(request):

    if request.method == 'POST':

        batch_name = request.POST.get('batch_name', '').strip()
        batch_description = request.POST.get('batch_description', '').strip()
        batch_price = request.POST.get('batch_price', '').strip()
        batch_status = request.POST.get('batch_status', '').strip()
        batch_thumbnail = request.FILES.get('batch_thumbnail')

        # Batch Name Validation

        if not batch_name:
            messages.error(request, 'Batch name is required.')
            return render(request, 'admins/batches/create_batch.html')

        if Batch.objects.filter(batch_name__iexact=batch_name).exists():
            messages.error(request, 'Batch name already exists.')
            return render(request, 'admins/batches/create_batch.html')

        # Description Validation

        if not batch_description:
            messages.error(request, 'Batch description is required.')
            return render(request, 'admins/batches/create_batch.html')

        # Price Validation

        if not batch_price:
            messages.error(request, 'Batch price is required.')
            return render(request, 'admins/batches/create_batch.html')

        try:
            batch_price = Decimal(batch_price)
        except InvalidOperation:
            messages.error(request, 'Enter a valid batch price.')
            return render(request, 'admins/batches/create_batch.html')

        if batch_price < 0:
            messages.error(request, 'Batch price cannot be negative.')
            return render(request, 'admins/batches/create_batch.html')

        # Status Validation

        if batch_status not in ['draft', 'published']:
            messages.error(request, 'Invalid batch status.')
            return render(request, 'admins/batches/create_batch.html')

        # Thumbnail Validation

        if not batch_thumbnail:
            messages.error(request, 'Batch thumbnail is required.')
            return render(request, 'admins/batches/create_batch.html')

        allowed_extensions = ['jpg', 'jpeg', 'png', 'webp']

        extension = batch_thumbnail.name.split('.')[-1].lower()

        if extension not in allowed_extensions:
            messages.error(request, 'Only JPG, JPEG, PNG and WEBP images are allowed.')
            return render(request, 'admins/batches/create_batch.html')

        # Maximum 5 MB

        if batch_thumbnail.size > 5 * 1024 * 1024:
            messages.error(request, 'Thumbnail must be less than 5 MB.')
            return render(request, 'admins/batches/create_batch.html')

        # Create Batch

        Batch.objects.create(
            batch_name=batch_name,
            batch_description=batch_description,
            batch_price=batch_price,
            batch_status=batch_status,
            batch_thumbnail=batch_thumbnail,
        )

        messages.success(request, 'Batch created successfully.')

        return redirect('admin_batches')
    
    return render(request, 'admins/batches/create_batch.html')


@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def edit_batch_view(request, batch_id):

    batch = get_object_or_404(Batch, id=batch_id)

    if request.method == 'POST':

        batch_name = request.POST.get('batch_name', '').strip()
        batch_description = request.POST.get('batch_description', '').strip()
        batch_price = request.POST.get('batch_price', '').strip()
        batch_status = request.POST.get('batch_status', '').strip()
        batch_thumbnail = request.FILES.get('batch_thumbnail')

        # Batch Name

        if not batch_name:
            messages.error(request, 'Batch name is required.')
            return render(
                request,
                'admins/batches/edit_batch.html',
                {'batch': batch}
            )

        if Batch.objects.filter(
            batch_name__iexact=batch_name
        ).exclude(id=batch.id).exists():

            messages.error(request, 'Batch name already exists.')

            return render(
                request,
                'admins/batches/edit_batch.html',
                {'batch': batch}
            )

        # Description

        if not batch_description:

            messages.error(request, 'Batch description is required.')

            return render(
                request,
                'admins/batches/edit_batch.html',
                {'batch': batch}
            )

        # Price

        if not batch_price:

            messages.error(request, 'Batch price is required.')

            return render(
                request,
                'admins/batches/edit_batch.html',
                {'batch': batch}
            )

        try:

            batch_price = Decimal(batch_price)

        except InvalidOperation:

            messages.error(request, 'Enter a valid batch price.')

            return render(
                request,
                'admins/batches/edit_batch.html',
                {'batch': batch}
            )

        if batch_price < 0:

            messages.error(request, 'Batch price cannot be negative.')

            return render(
                request,
                'admins/batches/edit_batch.html',
                {'batch': batch}
            )

        # Status

        if batch_status not in ['draft', 'published']:

            messages.error(request, 'Invalid batch status.')

            return render(
                request,
                'admins/batches/edit_batch.html',
                {'batch': batch}
            )

        # Thumbnail Validation (only if uploading new image)

        if batch_thumbnail:

            allowed_extensions = ['jpg', 'jpeg', 'png', 'webp']

            extension = batch_thumbnail.name.split('.')[-1].lower()

            if extension not in allowed_extensions:

                messages.error(
                    request,
                    'Only JPG, JPEG, PNG and WEBP images are allowed.'
                )

                return render(
                    request,
                    'admins/batches/edit_batch.html',
                    {'batch': batch}
                )

            if batch_thumbnail.size > 5 * 1024 * 1024:

                messages.error(
                    request,
                    'Thumbnail must be less than 5 MB.'
                )

                return render(
                    request,
                    'admins/batches/edit_batch.html',
                    {'batch': batch}
                )

            batch.batch_thumbnail = batch_thumbnail

        # Update Fields

        batch.batch_name = batch_name
        batch.batch_description = batch_description
        batch.batch_price = batch_price
        batch.batch_status = batch_status

        batch.save()

        messages.success(request, 'Batch updated successfully.')

        return redirect('admin_batches')

    return render(request,'admins/batches/edit_batch.html',{'batch': batch})


@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def delete_batch_view(request, batch_id):

    batch = get_object_or_404(Batch, id=batch_id)

    if request.method == "POST":

        confirm_name = request.POST.get("confirm_name", "").strip()

        # EMPTY FIELD VALIDATION

        if not confirm_name:

            messages.error(
                request,
                "Please enter the batch name to confirm deletion."
            )

            return render(
                request,
                "admins/batches/delete_batch.html",
                {
                    "batch": batch
                }
            )

        # BATCH NAME MATCH VALIDATION

        if confirm_name != batch.batch_name:

            messages.error(
                request,
                "Batch name does not match."
            )

            return render(
                request,
                "admins/batches/delete_batch.html",
                {
                    "batch": batch
                }
            )

        # DELETE CLOUDINARY IMAGE

        if batch.batch_thumbnail:

            batch.batch_thumbnail.delete(save=False)

        # DELETE BATCH

        batch.delete()

        messages.success(
            request,
            "Batch deleted successfully."
        )

        return redirect("admin_batches")

    return render(request,"admins/batches/delete_batch.html",{"batch": batch})



