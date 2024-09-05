from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseBadRequest
from external_accounts.models import CitesphereItem
from ..models import ImportedCitesphereItem, TextCollection
from django.contrib.auth.decorators import login_required

@login_required
def import_citesphere_items_from_group(request, citesphere_item_id, project_id):

    project = get_object_or_404(TextCollection, id=project_id)
    citesphere_item = get_object_or_404(CitesphereItem, id=citesphere_item_id)

    try:
        # Create the ImportedCitesphereItem
        imported_item = ImportedCitesphereItem.objects.create(
            user=request.user,
            citesphere_item=citesphere_item,
            project=project,
            source="Citesphere",
            processing_notes="Imported from group."
        )
        return redirect('view_project', project_id=project_id)
    except Exception as e:
        # In case of any error during creation, return a bad request response
        return HttpResponseBadRequest(f"An error occurred during import: {str(e)}")
