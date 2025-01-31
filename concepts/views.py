from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.template import loader
from django.urls import reverse
from concepts.models import Concept, Type
from concepts.filters import *
from concepts.lifecycle import *
from annotations.models import RelationSet, Appellation, TextCollection, VogonUserDefaultProject
from django.shortcuts import render, get_object_or_404, redirect
from concepts.authorities import ConceptpowerAuthority, update_instance
from django.contrib.auth.decorators import login_required
from concepts.decorators import conceptpower_login_required
import re, urllib.request, urllib.parse, urllib.error, string
from unidecode import unidecode
from urllib.parse import urlencode
from concepts.forms import ConceptpowerAuthForm
from .models import ConceptpowerAccount
from django.contrib import messages



def list_concept_types(request):
    """
    List all of the concept types
    """
    types = Type.objects.all().values('label', 'description', 'id')
    # types = Concept.objects.exclude(typed__isnull=True).values('typed__label','typed').distinct()

    template = "annotations/concept_types.html"
    context = {
        'types': types,
        'user': request.user,
    }
    return render(request, template, context)


def type(request, type_id):
    """
    Fetch description about type
    """
    instance = Type.objects.get(pk=type_id)

    examples  = Concept.objects.filter(typed__id=type_id, concept_state=Concept.RESOLVED).values('id', 'label', 'description')
    template = "annotations/concept_type_detail.html"
    context = {
        'type': instance,
        'user': request.user,
        'examples': examples[:20],
    }
    return render(request, template, context)

@staff_member_required
@conceptpower_login_required
def merge_concepts(request, source_concept_id):
    source = get_object_or_404(Concept, pk=source_concept_id)
    manager = ConceptLifecycle(source)
    target_uri = request.GET.get('target')
    manager.merge_with(target_uri)

    next_page = request.GET.get('next', reverse('concepts'))

    return HttpResponseRedirect(next_page)

@login_required
def concepts(request):
    """
    List all concepts.
    """
    qs = Concept.objects.filter(appellation__isnull=False).distinct('id').order_by('-id')

    filtered = ConceptFilter(request.GET, queryset=qs)
    qs = filtered.qs

    paginator = Paginator(qs, 20)
    page = request.GET.get('page')

    data = filtered.form.cleaned_data
    params_data = {}
    for key, value in list(data.items()):
        if key in ('typed'):
           if value is not None and hasattr(value, 'id'):
               params_data[key] = value.id
        elif value is not None:
            params_data[key] = value

    try:
        concepts = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        concepts = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        concepts = paginator.page(paginator.num_pages)

    context = {
        'paginator': paginator,
        'concepts': concepts,
        'filter': filtered,
        'path': urllib.parse.quote_plus(request.path + '?' + request.GET.urlencode()),
        'params_data': urlencode(params_data),
    }

    return render(request, 'annotations/concepts.html', context)


def concept(request, concept_id):
    """
    Details about a :class:`.Concept`\, including its associated annotations.
    """

    concept = get_object_or_404(Concept, pk=concept_id)
    context = {
        'concept': concept,
        'relations': RelationSet.objects.filter(terminal_nodes=concept).order_by('-created')[:10]
    }
    return render(request, "annotations/concept_details.html", context)


@conceptpower_login_required
@staff_member_required
def add_concept(request, concept_id):

    concept = get_object_or_404(Concept, pk=concept_id)
    manager = ConceptLifecycle(concept)
    next_page = request.GET.get('next', reverse('concepts'))
    back_to_page = request.GET.get('next')
    context = {
        'concept': concept,
        'next_page': urllib.parse.quote_plus(next_page),
        'back_to_page': back_to_page
    }
    if concept.concept_state != Concept.PENDING:
        return HttpResponseRedirect(next_page)

    if request.GET.get('confirmed', False):
        try:
            manager.add()
        except ConceptUpstreamException as E:
            return HttpResponse("Conceptpower is causing all kinds of problems"
                                " right now: %s" % str(E), status=500)
        return HttpResponseRedirect(next_page)


    candidates = manager.get_similar()
    matches = manager.get_matching()

    context.update({
        'candidates': candidates,
        'matches': matches,
    })

    return render(request, "annotations/concept_add.html", context)


@staff_member_required
@conceptpower_login_required
def edit_concept(request, concept_id):
    from concepts.forms import ConceptForm

    concept = get_object_or_404(Concept, pk=concept_id)
    next_page = request.GET.get('next', reverse('concept', args=(concept_id,)))

    if request.method == 'POST':
        form = ConceptForm(request.POST, instance=concept)
        if form.is_valid():
            form.save()
        return HttpResponseRedirect(next_page)
    if request.method == 'GET':
        form = ConceptForm(instance=concept)
    context = {
        'form': form,
        'concept': concept,
        'next_page': urllib.parse.quote_plus(next_page),
    }
    return render(request, "annotations/concept_edit.html", context)



@login_required
def sandbox(request, text_id):
    from annotations.models import RelationTemplate

    return render(request, "annotations/relationtemplate_creator.html", {})

@login_required
def conceptpower_login(request):
    if request.method == 'POST':
        # If using a custom Django Form:
        # form = ConceptPowerLoginForm(request.POST)
        # if form.is_valid():
        #     username = form.cleaned_data['username']
        #     password = form.cleaned_data['password']
        # else:
        #     messages.error(request, "Invalid form submission.")
        #     return render(request, 'conceptpower/login.html', {'form': form})

        # Or if not using a form:
        print(request.POST,"in conceptpower_login")
        username = request.POST.get('username')
        password = request.POST.get('password')
        print(username, password)   

        if not username or not password:
            messages.error(request, "Username and password are required.")
            return render(request, 'login/login.html')

        # You can now do your logic: store or validate with a remote service, etc.
        # If storing locally:
        account, created = ConceptpowerAccount.objects.get_or_create(user=request.user)
        account.username = username
        account.set_conceptpower_password(password)
        account.save()

        messages.success(request, "ConceptPower credentials saved!")
        next_url = request.POST.get('next', reverse('concepts'))
        return redirect(next_url)

    else:
        # If GET request, just show the empty form
        # form = ConceptPowerLoginForm()
        return render(request, 'login/login.html')