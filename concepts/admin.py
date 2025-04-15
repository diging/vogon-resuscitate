from django.contrib import admin
from .models import *

class ConceptAdmin(admin.ModelAdmin):
    model = Concept
    search_fields = ('label',)
    list_display = ('label', 'description', 'concept_state', 'typed', 'createdBy',)
    list_filter = ('concept_state', 'typed',)

    # def get_queryset(self, request):
    #     """
    #     Only show Rejected concepts if explicitly requested via the changelist
    #     filter.
    #     """
    #     qs = super(ConceptAdmin, self).get_queryset(request)
    #     if request.GET.get('concept_state__exact', None) == 'Rejected':
    #         return qs
    #     return qs.filter(~Q(concept_state=Concept.REJECTED))


class TypeAdmin(admin.ModelAdmin):
    model = Type
    list_display = ('label', 'resolved',)


class CommentAdmin(admin.ModelAdmin):
    model = Comment
    list_display = ('concept', 'text', 'created_by', 'created_at')
    list_filter = ('created_at', 'created_by')
    search_fields = ('text', 'concept__label')
    readonly_fields = ('created_at',)


admin.site.register(Concept, ConceptAdmin)
admin.site.register(Type, TypeAdmin)
admin.site.register(Comment, CommentAdmin)
