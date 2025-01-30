"""
Provides views related to external repositories.
"""

from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.db.models import Q
from django.contrib.auth.models import AnonymousUser
from django.conf import settings

from annotations.forms import RepositorySearchForm
from annotations.tasks import tokenize
from repository.models import Repository
from repository.auth import *
from repository.managers import *
from annotations.models import Text, TextCollection
from annotations.annotators import supported_content_types
from annotations.tasks import tokenize
from annotations.utils import get_pagination_metadata

from django.http import JsonResponse
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

from urllib.parse import urlparse, parse_qs
from urllib.parse import urlencode
from external_accounts.utils import parse_iso_datetimes

from external_accounts.decorators import citesphere_authenticated
from annotations.utils import get_pagination_metadata

import logging
logger = logging.getLogger(__name__)

import traceback

def _get_params(request):
    # The request may include parameters that should be passed along to the
    #  repository -- at this point, this is just for pagination.
    # TODO: restable should be taking care of this.
    params = request.GET.get('params', {})
    if params:
        params = dict([p.split(':') for p in params.split('|')])

    # Filter resources by the annotators available in this application.
    params.update({'content_type': supported_content_types()})
    return params


def _get_pagination(response, base_url, base_params):
    # TODO: restable should handle pagination, but it seems to be broken right
    #  now. Once that's fixed, we should back off and let restable do the work.
    if not response:
        return None, None
    _next_raw = response.get('next', None)
    if _next_raw:
        _params = {k: v[0] if isinstance(v, list) and len(v) > 0 else v
                   for k, v in list(parse_qs(urlparse(_next_raw).query).items())}
        _next = '|'.join([':'.join(o) for o in list(_params.items())])
        _nparams = {'params': _next}
        _nparams.update(base_params)
        next_page = base_url + '?' + urlencode(_nparams)

    else:
        next_page = None
    _prev_raw = response.get('previous', None)
    if _prev_raw:
        _params = {k: v[0] if isinstance(v, list) and len(v) > 0 else v
                   for k, v in list(parse_qs(urlparse(_prev_raw).query).items())}
        _prev = '|'.join([':'.join(o) for o in list(_params.items())])
        _nparams = {'params': _prev}
        _nparams.update(base_params)
        previous_page = base_url + '?' + urlencode(_nparams)
    else:
        previous_page = None
    return previous_page, next_page


# Since in citesphere_authenticated we already have a login_required decorator, we don't need to add another one here
@citesphere_authenticated
def repository_collections(request, repository_id):
    """View to fetch and display Citesphere Groups"""
    repository = get_object_or_404(Repository, pk=repository_id)
    manager = RepositoryManager(user=request.user, repository=repository)
    project_id = request.GET.get('project_id')

    try:
        collections = manager.groups()  # Fetch collections
    except CitesphereAPIError as e:
        print(traceback.format_exc())
        return render(request, 'annotations/repository_ioerror.html', {'error': str(e)}, status=500)
    except Exception as e:
        print(traceback.format_exc())
        return render(request, 'annotations/repository_ioerror.html', {'error': 'An unexpected error occurred'}, status=500)

    context = {
        'collections': collections,
        'repository':repository,
        'project_id':project_id,
    }

    return render(request, "annotations/repository_collections.html", context)


@citesphere_authenticated
def repository_collection(request, repository_id, group_id):
    """View to fetch and display collections and group texts within Citesphere Groups"""
    params = _get_params(request)

    repository = get_object_or_404(Repository, pk=repository_id)
    
    manager = RepositoryManager(user=request.user, repository=repository)

    page = int(request.GET.get('page', 1))
    
    try:
        response_data = manager.collections(group_id=group_id)
        group_info = response_data.get('group')
        collections = response_data.get('collections', [])
        group_texts = manager.group_items(group_id=group_id, page=page)
    except CitesphereAPIError as e:
        print(traceback.format_exc())
        return render(request, 'annotations/repository_ioerror.html', {'error': str(e)}, status=500)
    except Exception as e:
        print(traceback.format_exc())
        return render(request, 'annotations/repository_ioerror.html', {'error': 'An unexpected error occurred'}, status=500)

    project_id = request.GET.get('project_id')
    
    items_per_page = settings.PAGINATION_PAGE_SIZE
    pagination = get_pagination_metadata(total_items=group_texts.get('total_items'), page=page, items_per_page=items_per_page)
    
    base_params = {}
    if project_id:
        base_params.update({'project_id': project_id})

    context = {
        'user': request.user,
        'repository': repository,
        'group': group_info,
        'group_id': group_id,
        'collections': collections,
        'title': f'Browse collections in {group_id}',
        'project_id': project_id,
        'group_texts': group_texts['items'],
        'current_page': pagination['current_page'],
        'total_pages': pagination['total_pages'],
        'page_range': pagination['page_range'],
        'APP_ROOT': settings.APP_ROOT,        
    }

    return render(request, 'annotations/repository_collection.html', context)


@citesphere_authenticated
def repository_browse(request, repository_id):
    params = _get_params(request)

    repository = get_object_or_404(Repository, pk=repository_id)
    manager = RepositoryManager(user=request.user, repository=repository)
    project_id = request.GET.get('project_id')
    try:
        resources = manager.list(**params)
    except CitesphereAPIError as e:
        print(traceback.format_exc())
        return render(request, 'annotations/repository_ioerror.html', {'error': str(e)}, status=500)
    except Exception as e:
        print(traceback.format_exc())
        return render(request, 'annotations/repository_ioerror.html', {'error': 'An unexpected error occurred'}, status=500)

    base_url = reverse('repository_browse', args=(repository_id,))
    base_params = {}
    if project_id:
        base_params.update({'project_id': project_id})


    context = {
        'user': request.user,
        'repository': repository,
        'manager': manager,
        'title': 'Browse repository %s' % repository.name,
        'project_id': project_id,
        'resources': resources['resources'],
    }
    previous_page, next_page = _get_pagination(resources, base_url, base_params)
    if next_page:
        context.update({'next_page': next_page})
    if previous_page:
        context.update({'previous_page': previous_page})

    return render(request, 'annotations/repository_browse.html', context)


@citesphere_authenticated
def repository_search(request, repository_id):
    repository = get_object_or_404(Repository, pk=repository_id)
    query = request.GET.get('query', '')
    project_id = request.GET.get('project_id')
    form = RepositorySearchForm(request.GET)

    if query:
        texts = repository.texts.filter(
            Q(title__icontains=query)
        )
    else:
        # No query provided, so no texts to display
        texts = Text.objects.none()

    base_url = reverse('repository_search', args=(repository_id,))
    base_params = {'project_id': project_id} if project_id else {}

    # Context to pass to the template
    context = {
        'user': request.user,
        'repository': repository,
        'title': f'Search in repository {repository.name}',
        'form': form,
        'texts': texts,
        'query': query,
        'project_id': project_id,
    }

    return render(request, 'annotations/repository_search.html', context)

@login_required
def repository_list(request):
    template = "annotations/repository_list.html"
    project_id = request.GET.get('project_id')
    context = {
        'user': request.user,
        'repositories': Repository.objects.all(),
        'title': 'Repositories',
        'project_id': project_id,

    }

    return render(request, template, context)

@citesphere_authenticated
def repository_details(request, repository_id):
    template = "annotations/repository_details.html"
    repository = get_object_or_404(Repository, pk=repository_id)
    user = None if isinstance(request.user, AnonymousUser) else request.user

    texts_by_project = {}

    # Get projects where user is owner or collaborator
    user_collections = TextCollection.objects.filter(
        Q(ownedBy=user) | Q(collaborators=user)
    ).distinct()

    for collection in user_collections:
        # Filter texts within each collection that belong to the repository
        collection_texts = collection.texts.filter(repository=repository).order_by('-added')
        if collection_texts.exists():
            paginator = Paginator(collection_texts, settings.REPOSITORY_TEXT_PAGINATION_PAGE_SIZE)
            try:
                paginated_texts = paginator.page(request.GET.get('page', 1))
            except PageNotAnInteger:
                paginated_texts = paginator.page(1)
            except EmptyPage:
                paginated_texts = paginator.page(paginator.num_pages)
            texts_by_project[collection] = paginated_texts

    manager = RepositoryManager(user=user, repository=repository)

    context = {
        'user': user,
        'repository': repository,
        'manager': manager,
        'title': f'Repository details: {repository.name}',
        'texts_by_project': texts_by_project,
        'project_id': request.GET.get('project_id'),
        'page': request.GET.get('page', 1),
    }

    return render(request, template, context)


@citesphere_authenticated
def repository_collection_texts(request, repository_id, group_id, group_collection_id):
    """View to fetch and display paginated texts within a collection from Citesphere."""
    user = request.user
    repository = get_object_or_404(Repository, pk=repository_id)
    manager = RepositoryManager(user=user, repository=repository)

    page = int(request.GET.get('page', 1))

    try:
        texts = manager.collection_items(group_id, group_collection_id, page=page)
    except CitesphereAPIError as e:
        print(traceback.format_exc())
        return render(request, 'annotations/repository_ioerror.html', {'error': str(e)}, status=500)
    except Exception as e:
        print(traceback.format_exc())
        return render(request, 'annotations/repository_ioerror.html', {'error': 'An unexpected error occurred'}, status=500)

    # retrieve items per page from settings and calculate pagination metadata from util function
    items_per_page = settings.PAGINATION_PAGE_SIZE
    pagination = get_pagination_metadata(total_items=texts.get('total_items'), page=page, items_per_page=items_per_page)

    project_id = request.GET.get('project_id')
    context = {
        'user': user,
        'repository': repository,
        'texts': texts['items'],
        'title': 'Texts in Collection:',
        'group_info': texts['group'],
        'group_id': group_id,
        'project_id': project_id,
        'current_page': pagination['current_page'],
        'total_pages': pagination['total_pages'],
        'page_range': pagination['page_range'],
        'APP_ROOT': settings.APP_ROOT,
    }

    return render(request, 'annotations/repository_collections_text_list.html', context)


@citesphere_authenticated
def repository_text_files(request, repository_id, group_id, item_id):
    """View to fetch and return a dictionary of files for a specific text item."""
    user = request.user
    repository = get_object_or_404(Repository, pk=repository_id)
    manager = RepositoryManager(user=user, repository=repository)

    try:
        return JsonResponse(manager.item_files(group_id, item_id))
    except Exception as e:
        logger.error(f"Error accessing repository files: {str(e)}")
        return render(request, 'annotations/repository_ioerror.html', {'error': 'An error occurred while accessing the repository.'}, status=500)


@citesphere_authenticated
def repository_text_import(request, repository_id, group_id, text_key, file_id, project_id=None):

    if not project_id:
        return redirect(f"{reverse('list_projects')}?redirect_to_text_import=True&repository_id={repository_id}&group_id={group_id}&text_key={text_key}")

    # Retrieve the project directly using project_id from the URL
    project = get_object_or_404(TextCollection, pk=project_id)
    
    repository = get_object_or_404(Repository, pk=repository_id)
    manager = RepositoryManager(user=request.user, repository=repository)

    try:
        result = manager.item(group_id, text_key, file_id)
    except IOError as e:
        logger.error(f"Error accessing repository: {str(e)}")
        return render(request, 'annotations/repository_ioerror.html', {'error': 'There was an error accessing the repository.'}, status=500)

    item_details = result.get('item', {}).get('details', {})
    giles_text = result.get('item', {}).get('text')

    if not giles_text:
        return render(request, 'annotations/repository_ioerror.html', {'error': 'There was an error retrieving the content from Giles.'}, status=400)

    tokenized_content = tokenize(giles_text)

    # - urn:repository: prefix to identify this as a repository resource
    # - repository_id: to scope within a specific repository
    # - item_details.get('key'): the unique key for this item in the repository
    # - file_id: to identify the specific file, since an item can have multiple files
    unique_uri = f"urn:repository:{repository_id}:item:{item_details.get('key')}:file:{file_id}"

    defaults = {
        'title': item_details.get('title', 'Unknown Title'),
        'content_type': 'text/plain',  # Explicitly set to 'text/plain'
        'tokenizedContent': tokenized_content,
        'repository': repository,
        'repository_source_id': repository_id,
        'addedBy': request.user,
        'created': parse_iso_datetimes([item_details.get('addedOn')])[0],
        'originalResource': item_details.get('url'),
    }

    # Create or update the text in the database with the unique URI
    master_text, created = Text.objects.get_or_create(
        uri=unique_uri,
        defaults=defaults
    )

    if not created:
        # If the text already exists, update its tokenized content
        master_text.tokenizedContent = tokenized_content
        master_text.save()

    # Add text to project only if it's not already present
    if not project.texts.filter(pk=master_text.pk).exists():
        project.texts.add(master_text)
    
    return redirect(reverse('annotate', args=[master_text.id, project_id]))

@login_required
def repository_text_content(request, repository_id, text_id, content_id):

    repository = get_object_or_404(Repository, pk=repository_id)

    manager = RepositoryManager(user=request.user, repository=repository)
    # content_resources = {o['id']: o for o in resource['content']}
    # content = content_resources.get(int(content_id))    # Not a dict.
    try:
        content = manager.content(id=int(content_id))
        resource = manager.resource(id=int(text_id))
    except CitesphereAPIError as e:
        print(traceback.format_exc())
        return render(request, 'annotations/repository_ioerror.html', {'error': str(e)}, status=500)
    except Exception as e:
        print(traceback.format_exc())
        return render(request, 'annotations/repository_ioerror.html', {'error': 'An unexpected error occurred'}, status=500)

    content_type = content.get('content_type', None)
    from annotations import annotators
    if not annotators.annotator_exists(content_type):
        return _repository_text_fail(request, repository, resource, content)
    resource_text_defaults = {
        'title': resource.get('title'),
        'created': resource.get('created'),
        'repository': repository,
        'repository_source_id': repository_id,
        'addedBy': request.user,
    }
    part_of_id = request.GET.get('part_of')
    if part_of_id:
        try:
            master = manager.resource(id=int(part_of_id))
        except CitesphereAPIError as e:
            return render(request, 'annotations/repository_ioerror.html', {'error': str(e)}, status=500)
        except Exception as e:
            return render(request, 'annotations/repository_ioerror.html', {'error': 'An unexpected error occurred'}, status=500)
        master_resource, _ = Text.objects.get_or_create(uri=master['uri'],
                                                        defaults={
            'title': master.get('title'),
            'created': master.get('created'),
            'repository': repository,
            'repository_source_id': part_of_id,
            'addedBy': request.user,
        })
        resource_text_defaults.update({'part_of': master_resource})

    resource_text, _ = Text.objects.get_or_create(uri=resource['uri'],
                                                  defaults=resource_text_defaults)

    project_id = request.GET.get('project_id')
    if project_id:
        project = TextCollection.objects.get(pk=project_id)
    else:
        project = None

    action = request.GET.get('action', 'annotate')


    target, headers = content.get('location'), {}


    defaults = {
        'title': resource.get('title'),
        'created': resource.get('created'),
        'repository': repository,
        'repository_source_id': content_id,
        'addedBy': request.user,
        'content_type': content_type,
        'part_of': resource_text,
        'project':project,
        'originalResource': getattr(resource.get('url'), 'value', None),
    }
    text, _ = Text.objects.get_or_create(uri=content['uri'], defaults=defaults)
    if project_id:
        project.texts.add(text.top_level_text)

    if action == 'addtoproject' and project:
        return HttpResponseRedirect(reverse('view_project', args=(project_id,)))
    elif action == 'annotate':
        redirect = reverse('annotate', args=(text.id,))
        if project_id:
            redirect += '?project_id=%s' % str(project_id)
        return HttpResponseRedirect(redirect)


@login_required
def repository_text_add_to_project(request, repository_id, text_id, project_id):
    repository = get_object_or_404(Repository, pk=repository_id)
    project = get_object_or_404(TextCollection, pk=project_id)

    manager = RepositoryManager(user=request.user, repository=repository)

    defaults = {
        'repository': repository,
        'repository_source_id': text_id,
        'addedBy': request.user,
    }
    text, _ = Text.objects.get_or_create(pk=text_id)
    project.texts.add(text)
    return HttpResponseRedirect(reverse('view_project', args=(project_id,)))


def _repository_text_fail(request, repository, result, content):
    template = "annotations/repository_text_fail.html"
    project_id = request.GET.get('project_id')
    context = {
        'user': request.user,
        'repository': repository,
        'result': result,
        'content': content,
        'title': 'Whoops!',
        'content_type': content.get('content_type', None),
        'project_id': project_id,
    }
    return render(request, template, context)
