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
    return render(request,'admins/admin_signin.html')


@login_required(login_url='admin_signin')
@cache_control(no_cache=True,must_revalidate=True,no_store=True)
def admin_dashboard_view(request):

    # BLOCK NORMAL USERS
    if (not request.user.is_staff and not request.user.is_superuser):
        messages.error(request,'Access denied.')
        return redirect('admin_signin')

    response=render(request,'admins/dashboard.html')

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


@login_required(login_url='admin_signin')
@cache_control(no_cache=True,must_revalidate=True,no_store=True)
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

    return render(request,'admins/students.html',context)


@login_required(login_url='admin_signin')
def block_student_view(request,user_id):
    user=User.objects.get(id=user_id)
    if request.method=='POST':
        user.is_active=False
        user.save()
        messages.success(request,'Student blocked successfully.')
        return redirect('admin_students')
    return render(request,'admins/block_student.html',{'student':user})


@login_required(login_url='admin_signin')
def unblock_student_view(request,user_id):
    user=User.objects.get(id=user_id)
    if request.method=='POST':
        user.is_active=True
        user.save()
        messages.success(request,'Student unblocked successfully.')
        return redirect('admin_students')

    return render(request,'admins/unblock_student.html',{'student':user})


@login_required(login_url='admin_signin')
def delete_student_view(request,user_id):
    user=User.objects.get(id=user_id)
    if request.method=='POST':
        user.delete()
        messages.success(request,'Student deleted successfully.')
        return redirect('admin_students')

    return render(request,'admins/delete_student.html',{'student':user})