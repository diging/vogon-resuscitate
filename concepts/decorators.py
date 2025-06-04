from django.core.exceptions import PermissionDenied
from functools import wraps
from django.shortcuts import get_object_or_404
from concepts.models import Concept, Comment

def concept_access_required(view_func):
    """
    Decorator for views that checks if the user has access to the concept.
    A user has access if they are:
    1. The creator of the concept
    2. An admin or Vogon admin user
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        
        concept = None
        concept_id = kwargs.get('concept_id')
        comment_id = kwargs.get('comment_id')
        
        if concept_id:
            concept = get_object_or_404(Concept, pk=concept_id)
        elif comment_id:
            comment = get_object_or_404(Comment, pk=comment_id)
            concept = comment.concept
            
        if concept and (request.user == concept.createdBy or 
                       request.user.is_vogon_admin or request.user.is_staff):
            return view_func(request, *args, **kwargs)
            
        raise PermissionDenied("You do not have permission to access this concept.")
    return _wrapped_view 