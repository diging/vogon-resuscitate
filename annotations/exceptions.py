from django.http import HttpResponse
from django.template import loader
from django.shortcuts import render


def custom_403_handler(request, exception):
    """
    Default 403 Handler. This method gets invoked if a PermissionDenied
    Exception is raised.

    Parameters
    ----------
    request : `django.http.requests.HttpRequest`
    exception : Exception
        The PermissionDenied exception that was raised

    Returns
    ----------
    :class:`django.http.response.HttpResponse`
        Status 403.
    """
    template = loader.get_template('annotations/forbidden_error_page.html')
    
    # Get custom error message from the PermissionDenied exception
    # raise PermissionDenied("Custom message")
    error_message = str(exception) if exception else "Whoops, you're not supposed to be here!"
    
    context = {
        'userid': request.user.id,
        'error_message': error_message
    }
    
    return render(request, 'annotations/forbidden_error_page.html', context, status=403)