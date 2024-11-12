"""
Provides project (:class:`.TextCollection`) -related views.
"""

from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import login, authenticate
from django.conf import settings
from django.db.models import Q, Count

from annotations.models import TextCollection, RelationSet, VogonUser
from annotations.forms import ProjectForm

from django.contrib import messages
from django.http import Http404

def view_project(request, project_id):
    """
    Shows details about a specific project owned by the current user.

    Parameters
    ----------
    request : `django.http.requests.HttpRequest`
    project_id : int

    Returns
    ----------
    :class:`django.http.response.HttpResponse`
    """

    project = get_object_or_404(TextCollection, pk=project_id)
    template = "annotations/project_details.html"

    # Handle ordering
    order_by = request.GET.get('order_by', 'title')
    if order_by.startswith('-'):
        order_field = order_by[1:]
        order_direction = '-'
    else:
        order_field = order_by
        order_direction = ''

    # Validate order field is allowed
    allowed_order_fields = ['title', 'added']
    if order_field not in allowed_order_fields:
        order_field = 'title'
        order_direction = ''

    # Apply ordering
    order_param = f"{order_direction}{order_field}"
    texts = project.texts.all().order_by(order_param)\
                         .values('id', 'title', 'added', 'repository_source_id')

    paginator = Paginator(texts, 15)
    page = request.GET.get('page')
    try:
        texts = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        texts = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        texts = paginator.page(paginator.num_pages)

    from annotations.filters import RelationSetFilter

    # for now let's remove this; it takes long to load the pages and there is a bug somewhere
    # that throws an error sometimes [VGNWB-215]
    #filtered = RelationSetFilter({'project': project.id}, queryset=RelationSet.objects.all())
    #relations = filtered.qs

    context = {
        'user': request.user,
        'title': project.name,
        'project': project,
        'collaborators': project.collaborators.all(),
        'texts': texts,
        'order_by': order_by,
        # 'relations': relations,
    }

    return render(request, template, context)


@login_required
def edit_project(request, project_id):
    """
    Allow the owner of a project to edit it.

    Parameters
    ----------
    project_id : int
    request : `django.http.requests.HttpRequest`

    Returns
    ----------
    :class:`django.http.response.HttpResponse`
    """
    template = "annotations/project_change.html"
    project = get_object_or_404(TextCollection, pk=project_id)
    if project.ownedBy.id != request.user.id:
        raise PermissionDenied("Whoops, you're not supposed to be here!")

    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            redirect_target = reverse('view_project', args=(project.id,))
            return HttpResponseRedirect(redirect_target)
        else:
            print((form.errors))
    else:
        form = ProjectForm(instance=project)

    context = {
        'user': request.user,
        'title': 'Editing project: %s' % project.name,
        'project': project,
        'form': form,
        'page_title': 'Edit project'
    }
    return render(request, template, context)


@login_required
def create_project(request):
    """
    Create a new project owned by the current (logged-in) user.

    Parameters
    ----------
    request : `django.http.requests.HttpRequest`

    Returns
    ----------
    :class:`django.http.response.HttpResponse`
    """
    template = "annotations/project_change.html"

    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.ownedBy = request.user
            project.save()
            redirect_target = reverse('view_project', args=(project.id,))
            return HttpResponseRedirect(redirect_target)
        else:
            print((form.errors))
    else:
        form = ProjectForm()

    context = {
        'user': request.user,
        'title': 'Create a new project',
        'form': form,
        'page_title': 'Create a new project'
    }
    return render(request, template, context)


def list_projects(request):
    """
    All known projects.

    Parameters
    ----------
    project_id : int
    request : `django.http.requests.HttpRequest`

    Returns
    ----------
    :class:`django.http.response.HttpResponse`
    """

    fields = [
        'id',
        'name',
        'created',
        'ownedBy__id',
        'ownedBy__username',
        'description',
        'num_texts',
        'num_relations',
    ]
    qs = TextCollection.objects.all()
    qs = qs.annotate(num_texts=Count('texts'),
                     num_relations=Count('texts__relationsets'))
    qs = qs.values(*fields)

    template = "annotations/project_list.html"
    context = {
        'user': request.user,
        'title': 'Projects',
        'projects': qs,
    }
    return render(request, template, context)


@login_required
def add_collaborator(request, project_id):
    """
    Add a collaborator to a project. Only the project owner can add collaborators.
    
    Parameters
    ----------
    project_id : int
        ID of the project to add collaborator to
    request : django.http.requests.HttpRequest
        The request object containing the username of collaborator to add
        
    Returns
    -------
    django.http.response.HttpResponseRedirect
        Redirects back to project detail page after adding collaborator
        
    Raises
    ------
    PermissionDenied
        If user is not the project owner
    Http404
        If project or collaborator username not found
    """
    project = get_object_or_404(TextCollection, pk=project_id)
    if project.ownedBy != request.user:
        raise PermissionDenied("You do not have permission to add participants.")
    
    if request.method == 'POST':
        collaborator_username = request.POST.get('username')
        try:
            collaborator = get_object_or_404(VogonUser, username=collaborator_username)
            project.collaborators.add(collaborator)
            project.save()
            messages.success(request, f'Successfully added {collaborator_username} as a collaborator.')
        except Http404:
            messages.error(request, f'User {collaborator_username} not found.')
        return HttpResponseRedirect(reverse('view_project', args=[project_id]))
    

@login_required
def remove_collaborator(request, project_id):
    """
    Remove a collaborator from a project.

    Parameters
    ----------
    project_id : int
        ID of the project
    request : `django.http.requests.HttpRequest`

    Returns
    ----------
    :class:`django.http.response.HttpResponseRedirect`
    """
    project = get_object_or_404(TextCollection, pk=project_id)
    if project.ownedBy != request.user:
        raise PermissionDenied("You do not have permission to remove collaborators.")

    if request.method == 'POST':
        collaborator_username = request.POST.get('username')
        try:
            collaborator = get_object_or_404(VogonUser, username=collaborator_username)
            project.collaborators.remove(collaborator)
            project.save()
            messages.success(request, f'Successfully removed {collaborator_username} from the project.')
        except Http404:
            messages.error(request, f'User {collaborator_username} not found.')
        return HttpResponseRedirect(reverse('view_project', args=[project_id]))
