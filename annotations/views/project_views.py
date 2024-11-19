"""
Provides project (:class:`.TextCollection`) -related views.
"""

from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseRedirect
from django.conf import settings
from django.db.models import Q

from annotations.models import TextCollection, VogonUser
from annotations.forms import ProjectForm

from django.contrib import messages
from django.http import Http404

from annotations.utils import get_ordering_metadata, get_user_project_stats, _annotate_project_counts

@login_required
def view_project(request, project_id):
    """
    Shows details about a specific project owned by the current user.
    """
    project = get_object_or_404(
        _annotate_project_counts(TextCollection.objects),
        pk=project_id
    )

    # Check if user is owner or collaborator
    if not (request.user == project.ownedBy or request.user in project.collaborators.all()):
        raise PermissionDenied("Oops! Looks like you're trying to sneak a peek into someone else's project.")

    template = "annotations/project_details.html"

    # Get ordering metadata
    ordering = get_ordering_metadata(request, default_field='title', allowed_fields=['title', 'added'])

    # Apply ordering
    texts = project.texts.all().order_by(ordering['order_param'])\
                         .values('id', 'title', 'added')

    paginator = Paginator(texts, 15)
    page = request.GET.get('page')
    try:
        texts = paginator.page(page)
    except PageNotAnInteger:
        texts = paginator.page(1)
    except EmptyPage:
        texts = paginator.page(paginator.num_pages)

    # Get owner and collaborator stats
    owner_stats = get_user_project_stats(project.ownedBy, project)
    collaborator_stats = [get_user_project_stats(collaborator, project) for collaborator in project.collaborators.all()]

    context = {
        'user': request.user,
        'title': project.name,
        'project': project,
        'owner_stats': owner_stats,
        'collaborator_stats': collaborator_stats,
        'texts': texts,
        'order_by': ordering['order_by'],
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

@login_required
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
        'num_collaborators',
    ]
    
    # Get projects where user is owner or collaborator, and distinct to avoid duplicates
    qs = TextCollection.objects.filter(
        Q(ownedBy=request.user) | Q(collaborators=request.user)
    ).distinct()
    
    qs = _annotate_project_counts(qs)
    qs = qs.values(*fields)

    template = "annotations/project_list.html"
    context = {
        'user': request.user,
        'title': 'Projects',
        'projects': qs,
        'redirect_to_text_import': False,
    }

    # Check if the user is redirected from the repository text import view, this will be used to select the project for the text import
    if request.GET.get('redirect_to_text_import'):
        repository_id = request.GET.get('repository_id')
        group_id = request.GET.get('group_id')
        text_key = request.GET.get('text_key')

        context.update({
            'redirect_to_text_import': True,
            'repository_id': repository_id,
            'group_id': group_id,
            'title': 'Select a Project for to import this text:',
            'text_key': text_key
        })

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
            messages.success(request, f'Successfully added {collaborator_username} as a collaborator.', extra_tags='success')
        except Http404:
            messages.error(request, f'User {collaborator_username} not found.', extra_tags='danger')
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
