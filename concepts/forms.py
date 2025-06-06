from django import forms
from concepts.models import Concept, Type
from viapy.widgets import ViafURLWidget


class ConceptForm(forms.ModelForm):
    class Meta:
        model = Concept
        fields = ('uri', 'label', 'description', 'typed', )
        widgets = {
            'uri': ViafURLWidget(attrs={'class': 'form-control'}),
        }


class ConceptTypeForm(forms.Form):
    typed = forms.ModelChoiceField(queryset=Type.objects.all())
