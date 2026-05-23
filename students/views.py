from django.shortcuts import (
    render,
    redirect
)

from django.contrib.auth.decorators import (
    login_required
)

from django.views.decorators.cache import (
    cache_control
)

from django.contrib import messages


@login_required(login_url='signin')

@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True
)

def dashboard_view(request):

    # BLOCK STAFF / ADMIN USERS

    if (
        request.user.is_staff
        or
        request.user.is_superuser
    ):

        messages.error(
            request,
            (
                'Admin login is not allowed here. '
                'Please use the admin login area.'
            )
        )

        return redirect('signin')

    return render(
        request,
        'students/dashboard.html'
    )