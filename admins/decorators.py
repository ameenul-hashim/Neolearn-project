from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


def admin_required(view_func):

    @login_required(login_url='admin_signin')
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        if (not request.user.is_staff and not request.user.is_superuser):
            messages.error(request, 'Access denied.')
            return redirect('admin_signin')

        return view_func(request, *args, **kwargs)

    return wrapper