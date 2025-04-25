from annotations.models import (VogonUser, TextCollection, RelationTemplate, RelationTemplatePart, DefaultMapping,
    VogonGroup)
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError
from django import forms
from django.forms import widgets, BaseFormSet

from django.conf import settings

from django.utils.html import format_html
from django.forms.utils import flatatt
from django.utils.encoding import force_str
import networkx as nx
from concepts.conceptpower import Conceptpower
from concepts.models import Concept, Type

class RegistrationForm(forms.Form):
    """
    Gives user form of signup and validates it.
    """
    full_name = forms.CharField(required=True, max_length=30, label=_("Full name"))
    username = forms.RegexField(regex=r'^\w+$', widget=forms.TextInput(attrs=dict(required=True, max_length=30)),
                                label=_("Username"),
                                error_messages={ 'invalid': _("This value must contain only letters, "
                                                              "numbers and underscores.") })
    email = forms.EmailField(widget=forms.TextInput(attrs=dict(required=True, max_length=30)), label=_("Email address"))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs=dict(required=True, max_length=30,
                                                                      render_value=False)), label=_("Password"))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs=dict(required=True, max_length=30,
                                                                      render_value=False)), label=_("Password (again)"))
    affiliation = forms.CharField(required=True, max_length=30, label=_("Affliation"))
    location = forms.CharField(required=True, max_length=30, label=_("Location"))
    link = forms.URLField(required=True, max_length=500, label=_("Link"))


    def clean_username(self):
        """
        Validates username.
        """
        try:
            user = VogonUser.objects.get(username__iexact=self.cleaned_data['username'])
        except VogonUser.DoesNotExist:
            return self.cleaned_data['username']
        raise forms.ValidationError(_("The username already exists. Please try another one."))

    def clean(self):
        """
        Validates the values inserted in Password and Confirm Password field are same.
        """
        if 'password1' in self.cleaned_data and 'password2' in self.cleaned_data:
            if self.cleaned_data['password1'] != self.cleaned_data['password2']:
                raise forms.ValidationError(_("The two password fields did not match."))

def validatefiletype(file):
    """
    Validates type of uploaded file.

    Parameters
    ----------
    file : file
        The file that is uploaded.

    Raises
    ------
    ValidationError
        Raises this exception if uploaded file is neither plain text nor PDF
    """
    # TODO: add PDF back in once we have a better system in place for processing
    #  large uploads.
    if file.content_type != 'text/plain':    # file.content_type != 'application/pdf' and
        raise ValidationError('Please choose a plain text file')


class UploadFileForm(forms.Form):
    title = forms.CharField(max_length=255, required=True,
                            help_text='The title of the original resource.')
    uri = forms.CharField(label='URI', max_length=255, required=True,
                            help_text='"URI" stands for Uniform Resource Identifier. This can be a DOI, a permalink to a digital archive (e.g. JSTOR), or any other unique identifier.')
    ispublic = forms.BooleanField(label='Make this text public',
                required=False,
                help_text='By checking this box you affirm that you have the right to make this file publicly available.')
    filetoupload = forms.FileField(label='Choose a plain text file:',
                required=True,
                validators=[validatefiletype],
                help_text="Soon you'll be able to upload images, PDFs, and HTML documents!")
    datecreated = forms.DateField(label='Date created:',
                required=False,
                widget=forms.TextInput(attrs={'class':'datepicker'}),
                help_text='The date that the original resource was published.')

    project = forms.ModelChoiceField(queryset=TextCollection.objects.all(),
                                     required=False,
                                     label='Add to project',
                                     help_text='You can add this text to a project that you own.')


class UserCreationForm(forms.ModelForm):

    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput)

    class Meta:
        model = VogonUser
        fields = ('full_name', 'email', 'affiliation', 'location', 'link', 'imagefile')

    def clean_password2(self):
        # Check that the two password entries match
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        # Save the provided password in hashed format
        user = super(UserCreationForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):

    class Meta:
        model = VogonUser
        fields = ('full_name', 'email', 'affiliation', 'location', 'imagefile',
                   'link')

    def clean_password(self):
        # Regardless of what the user provides, return the initial value.
        # This is done here, rather than on the field, because the
        # field does not have access to the initial value
        return self.initial.get("password")


class AutocompleteWidget(widgets.TextInput):
    def _format_value(self, value):
        if self.is_localized:
            return formats.localize_input(value)
        return value

    def render(self, name, value, attrs=None, renderer=None):
        if value is None:
            value = ''
        final_attrs = {**self.attrs, **(attrs or {}), 'type': self.input_type, 'name': name}
        if value != '':
            # Only add the 'value' attribute if a value is non-empty.
            final_attrs['value'] = force_str(self._format_value(value))

        classes = 'autocomplete'
        if 'class' in final_attrs:
            classes += ' ' + final_attrs['class']

        return format_html('<input class="' + classes + '"{} />', flatatt(final_attrs))


class ConceptField(forms.CharField):
    queryset = Concept.objects.all()

    def label_from_instance(self, obj):
        """
        The ``_concept`` field should be populated with the :class:`.Concept`\s
        id.
        """
        return obj.uri

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            key = 'uri'
            py_value = self.queryset.get(**{key: value})
        except self.queryset.model.DoesNotExist:
            headers = {
                    'Accept': 'application/json',
            }
            conceptpower = Conceptpower(settings.CONCEPTPOWER_ENDPOINT, settings.CONCEPTPOWER_NAMESPACE)
            concept_entry = conceptpower.get(value, headers=headers)
            data = dict(
                uri=value,
                label=concept_entry.get('lemma',''),
                description=concept_entry.get('description',''),
                pos=concept_entry.get('pos',''),
                authority=concept_entry.get('authority',{'name': 'Conceptpower'}),
                concept_state=Concept.RESOLVED,
            )
            ctype_data = concept_entry.get('type','')
            if ctype_data:
                data.update({'typed': Type.objects.get_or_create(uri=ctype_data['type_uri'])[0]})
            py_value = Concept.objects.create(**data)
        return py_value
    
class TemplateChoiceField(forms.ChoiceField):
    def label_from_instance(self, obj):
        """
        The ``_concept`` field should be populated with the :class:`.Concept`\s
        id.
        """
        return obj.id


class ChoiceIntegerField(forms.IntegerField):
    """
    An :class:`.IntegerField` that plays well with the :class:`.Select` widget.
    """

    def to_python(self, value):
        """
        Validates that int() can be called on the input. If not, return -1
        (default value for ..._relationtemplate_internal_id fields).
        """
        try:
            value = value.split(':')[-1]
            int(value)
            return super(ChoiceIntegerField, self).to_python(value)
        except ValueError:
            return -1


# TODO: widget details (e.g. CSS classes) should be in the template.
class RelationTemplateForm(forms.ModelForm):
    # Hidden field to carry the PK of the DefaultMapping for this RelationTemplate (populates structured_mapping)
    structured_mapping = forms.ModelChoiceField(
        queryset=DefaultMapping.objects.all(),
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_structured_mapping'})
    )
    
    name = forms.CharField(widget=forms.TextInput(attrs={
            'class': 'form-control input-sm',
            'placeholder': 'What is this relation called?'
        }))
    description = forms.CharField(widget=forms.Textarea(attrs={
            'class': 'form-control input-sm',
            'rows': 2,
            'placeholder': 'Please describe this relation.',
        }))
    expression = forms.CharField(widget=forms.Textarea(attrs={
            'class': 'form-control input-sm',
            'rows': 3,
            'placeholder': "Enter an expression pattern for this relation."
                           " This should be a full-sentence structure that"
                           " expresses the content of the relation. Indicate"
                           " the position of nodes (concepts) in the template"
                           " using node identifiers, e.g. {0s} for the subject"
                           " of this first relation part, {1o} for the object"
                           " of the second part, or {2p} for the predicate of"
                           " the third part."
        }))
    terminal_nodes = forms.CharField(widget=forms.TextInput(attrs={
            'class': 'form-control input-sm',
            'rows': 2,
            'placeholder': "Enter comma-separated node identifiers. E.g."
                           " ``0s,1o``."
        }))
    
    # This is not directly a part of the RelationTemplate, this is used to populate DefaultMapping model which is connect through structured_mapping field using a ForeignKey
    first_node_type = forms.ChoiceField(required=True, choices=[('Node', 'Node'), ('URI', 'URI')], widget=forms.Select(attrs={
            'class': 'form-control input-sm node-type-dropdown',
            'id': 'first_node_type'
        }))
    first_node_value = forms.CharField(required=True, widget=forms.TextInput(attrs={
            'class': 'form-control input-sm',
            'id': 'first_node_value',
            'placeholder': 'Enter value'
        }))
    second_node_type = forms.ChoiceField(required=True, choices=[('Node', 'Node'), ('URI', 'URI')], widget=forms.Select(attrs={
            'class': 'form-control input-sm node-type-dropdown',
            'id': 'second_node_type'
        }))
    second_node_value = forms.CharField(required=True, widget=forms.TextInput(attrs={
            'class': 'form-control input-sm',
            'id': 'second_node_value',
            'placeholder': 'Enter value'
        }))
    third_node_type = forms.ChoiceField(required=True, choices=[('Node', 'Node'), ('URI', 'URI')], widget=forms.Select(attrs={
            'class': 'form-control input-sm node-type-dropdown',
            'id': 'third_node_type'
        }))
    third_node_value = forms.CharField(required=True, widget=forms.TextInput(attrs={
            'class': 'form-control input-sm',
            'id': 'third_node_value',
            'placeholder': 'Enter value'
        }))
    
    class Meta:
        model = RelationTemplate
        fields = ['name', 'description', 'expression', 'terminal_nodes', 'structured_mapping',
                 'first_node_type', 'first_node_value', 
                 'second_node_type', 'second_node_value', 
                 'third_node_type', 'third_node_value']
    
    def clean_expression(self):
        """
        Validates expression field. Expression is always required.
        """
        expression = self.cleaned_data.get('expression')
        if not expression:
            raise forms.ValidationError("Expression is required")
        return expression
        

    def clean_terminal_nodes(self):
        value = self.cleaned_data.get('terminal_nodes')
        # Handle empty value for the case where there are no Nodes (all URIs)
        if not value:
            return value
        
        try:
            # Skip validation if empty
            if not value:
                return value
                
            # Otherwise validate normally
            for u, v in map(tuple, value.split(',')):
                pass
        except Exception as E:
            raise ValidationError('Invalid terminal nodes')
        return value
    
    def __init__(self, *args, **kwargs):
        super(RelationTemplateForm, self).__init__(*args, **kwargs)
        
        # If we're editing an existing instance with a structured_mapping
        if self.instance and self.instance.pk and self.instance.structured_mapping:
            # Populate the relation node fields from the structured mapping
            mapping = self.instance.structured_mapping
            self.initial['first_node_type'] = mapping.subject_type
            self.initial['first_node_value'] = mapping.subject_value
            self.initial['second_node_type'] = mapping.predicate_type
            self.initial['second_node_value'] = mapping.predicate_value
            self.initial['third_node_type'] = mapping.object_type
            self.initial['third_node_value'] = mapping.object_value

    def save(self, commit=True):
        instance = super(RelationTemplateForm, self).save(commit=False)
        
        # Process relation nodes and create a DefaultMapping
        first_node_type = self.cleaned_data.get('first_node_type')
        first_node_value = self.cleaned_data.get('first_node_value')
        second_node_type = self.cleaned_data.get('second_node_type')
        second_node_value = self.cleaned_data.get('second_node_value')
        third_node_type = self.cleaned_data.get('third_node_type')
        third_node_value = self.cleaned_data.get('third_node_value')
        
        # Create or update the DefaultMapping
        if instance.structured_mapping:
            # Update existing mapping
            mapping = instance.structured_mapping
            mapping.subject_type = first_node_type
            mapping.subject_value = first_node_value
            mapping.predicate_type = second_node_type
            mapping.predicate_value = second_node_value
            mapping.object_type = third_node_type
            mapping.object_value = third_node_value
            mapping.save()
        else:
            # Create new mapping
            mapping = DefaultMapping.objects.create(
                subject_type=first_node_type,
                subject_value=first_node_value,
                predicate_type=second_node_type,
                predicate_value=second_node_value,
                object_type=third_node_type,
                object_value=third_node_value
            )
            instance.structured_mapping = mapping
        
        # Update terminal nodes from relation nodes
        terminal_nodes = []
        if first_node_type == 'Node':
            terminal_nodes.append(first_node_value)
        if second_node_type == 'Node':
            terminal_nodes.append(second_node_value)
        if third_node_type == 'Node':
            terminal_nodes.append(third_node_value)
        
        # Set terminal nodes if there are any
        if terminal_nodes:
            instance.terminal_nodes = ','.join(terminal_nodes)
        
        if commit:
            instance.save()
        
        return instance


class UberCheckboxInput(forms.CheckboxInput):
    def value_from_datadict(self, data, files, name):
        """
        For some stupid reason, some checked checkboxes are getting passed as
        '', and :class:`forms.CheckboxInput` stupidly calls these values False.
        So, we fix that. If the field is present in the POST data, then it is
        True. Grrrr.
        """
        if name not in data:
        # A missing value means False because HTML form submission does not
        # send results for unselected checkboxes.
            return False
        return True


# TODO: styling (CSS classes) should be in the template.
# TODO: Move away from the AutocompleteWidget; too janky.
class RelationTemplatePartForm(forms.ModelForm):
    """

    TODO: make sure that there are no self-loops in inter-part references.
    """
    source_concept = ConceptField(widget=widgets.HiddenInput(), required=False)
    source_concept_description = forms.CharField(widget=forms.Textarea(attrs={
        'class': 'form-control input-sm',
        'rows': 2,
        'disabled': True,
        'readonly': True,
        'style': 'visibility: hidden;'
    }), required=False)
    source_node_type = forms.ChoiceField(choices=[('', 'Select a node type')] + list(RelationTemplatePart.NODE_CHOICES), required=True,
                                         widget=widgets.Select(attrs={'class': 'form-control input-sm node_type_field', 'part': 'source'}))

    source_concept_text = forms.CharField(widget=AutocompleteWidget(attrs={'target': 'source_concept', 'results-target': 'source_concept_results_elem', 'status-target': 'source_concept_status_elem', 'description': 'source_concept_description'}), required=False)
    source_prompt_text = forms.BooleanField(required=False, initial=True, widget=UberCheckboxInput())
    source_description = forms.CharField(widget=forms.Textarea(attrs={
            'class': 'form-control input-sm',
            'rows': 2,
            'placeholder': 'Any additional explanatory information, to be displayed to the user.',
        }), required=False)

    predicate_concept = ConceptField(widget=widgets.HiddenInput(), required=False)
    predicate_concept_description = forms.CharField(widget=forms.Textarea(attrs={
        'class': 'form-control input-sm',
        'rows': 2,
        'disabled': True,
        'readonly': True,
        'style': 'visibility: hidden;'
    }), required=False)
    predicate_node_type = forms.ChoiceField(choices=[('', 'Select a node type')] + list(RelationTemplatePart.PRED_CHOICES), required=True,
                                            widget=widgets.Select(attrs={'class': 'form-control input-sm node_type_field', 'part': 'predicate'}))
    predicate_concept_text = forms.CharField(widget=AutocompleteWidget(attrs={'target': 'predicate_concept', 'results-target': 'predicate_concept_results_elem', 'status-target': 'predicate_concept_status_elem', 'description': 'predicate_concept_description'}), required=False)
    predicate_prompt_text = forms.BooleanField(required=False, initial=True, widget=UberCheckboxInput())
    predicate_description = forms.CharField(widget=forms.Textarea(attrs={
            'class': 'form-control input-sm',
            'rows': 2,
            'placeholder': 'Any additional explanatory information, to be displayed to the user.',
        }), required=False)

    object_concept = ConceptField(widget=widgets.HiddenInput(), required=False)
    object_node_type = forms.ChoiceField(choices=[('', 'Select a node type')] + list(RelationTemplatePart.NODE_CHOICES), required=True,
                                         widget=widgets.Select(attrs={'class': 'form-control input-sm node_type_field', 'part': 'object'}))
    object_concept_text= forms.CharField(widget=AutocompleteWidget(attrs={'target': 'object_concept', 'results-target': 'object_concept_results_elem', 'status-target': 'object_concept_status_elem', 'description': 'object_concept_description'}), required=False)
    object_prompt_text = forms.BooleanField(required=False, initial=True, widget=UberCheckboxInput())
    object_description = forms.CharField(widget=forms.Textarea(attrs={
            'class': 'form-control input-sm',
            'rows': 2,
            'placeholder': 'Any additional explanatory information, to be displayed to the user.',
        }), required=False)
    object_concept_description = forms.CharField(widget=forms.Textarea(attrs={
        'class': 'form-control input-sm',
        'rows': 2,
        'disabled': True,
        'readonly': True,
        'style': 'visibility: hidden;'
    }), required=False)

    source_relationtemplate_internal_id = ChoiceIntegerField(required=False, widget=widgets.NumberInput(attrs={'placeholder': 'The ID of a relation in this template.'}))
    object_relationtemplate_internal_id = ChoiceIntegerField(required=False, widget=widgets.NumberInput(attrs={'placeholder': 'The ID of a relation in this template.'}))

    internal_id = forms.IntegerField(widget=widgets.HiddenInput())

    class Media:
        # js = ('annotations/js/autocomplete.js',)
        css = {
            'all': ['annotations/css/autocomplete.css']
        }

    class Meta:
        model = RelationTemplatePart
        exclude = [
            'source_relationtemplate',
            'object_relationtemplate',
            'part_of',
            ]
        autocomplete_fields = (    # TODO: do we need this?
            'source_concept',
            'predicate_concept',
            'object_concept',
            )

    def __init__(self, *args, **kwargs):
        super(RelationTemplatePartForm, self).__init__(*args, **kwargs)

        # We need a bit of set-up for angular data bindings to work properly
        #  on the form.
        # Angular can't handle hyphens, so we use underscores.
        self.safe_prefix = self.prefix.replace('-', '_')

        self.ident = self.prefix.split('-')[-1]
        self.fields['internal_id'].initial = self.ident

        for fname, field in list(self.fields.items()):
            if 'prompt_text' in fname:
                continue
            if 'class' not in field.widget.attrs:
                field.widget.attrs.update({'class': 'form-control input-sm'})

            for name in ['target', 'results-target', 'status-target']:
                if name in field.widget.attrs:
                    field.widget.attrs[name] = 'id_{0}-'.format(self.prefix) + field.widget.attrs[name]
            if 'description' in field.widget.attrs:
                field.widget.attrs['description'] = 'id_{0}-'.format(self.prefix) + field.widget.attrs['description']

    def clean(self, *args, **kwargs):

            
        for field in ['source', 'object']:
            selected_node_type = self.cleaned_data.get('%s_node_type' % field)
            # If the user has selected the "Concept type" field, then they must
            #  also provide a specific concept type.
            # if selected_node_type == 'TP':
            #     if not self.cleaned_data.get('%s_type' % field, None):
            #         self.add_error('%s_type' % field, 'Must select a concept type')

        for field in ['source', 'predicate', 'object']:
            evidence = self.cleaned_data.get('%s_prompt_text' % field)
            label = self.cleaned_data.get('%s_label' % field)
            selected_node_type = self.cleaned_data.get('%s_node_type' % field)
            if evidence and not label:
                if selected_node_type not in [RelationTemplatePart.RELATION, RelationTemplatePart.TOBE, RelationTemplatePart.HAS]:
                    self.add_error('%s_label' % field, 'Please add a label')
                
                
class RelationTemplatePartFormSet(BaseFormSet):
    """
    Ensure that the structure of the links among relation template parts is
    coherent: it must be acyclic, and the parts must all be connected.
    """
    def clean(self):
        if any(self.errors):
            return

        formGraph = nx.DiGraph()    # Dependency graph among parts.
        for form in self.forms:
            formGraph.add_node(form.cleaned_data['internal_id'])
            for field in ['source', 'object']:
                fieldname = '%s_relationtemplate_internal_id' % field
                target = form.cleaned_data[fieldname]
                if target > -1:
                    formGraph.add_edge(form.cleaned_data['internal_id'], target)

        if not nx.is_directed_acyclic_graph(formGraph):
            for form in self.forms:
                form.add_error(None, 'Circular reference among relation parts.')

        if not nx.is_connected(formGraph.to_undirected()):
            for form in self.forms:
                form.add_error(None, 'At least one relation part is disconnected from the rest of the relation.')




class ProjectForm(forms.ModelForm):
    """
    Gives the participants list for every collection.
    """

    class Meta:
        model = TextCollection
        exclude = ['ownedBy', 'texts', 'participants']

    # def __init__(self, *args, **kwargs):
    #     super(ProjectForm, self).__init__(*args, **kwargs)
    #     self.fields["participants"].widget = forms.CheckboxSelectMultiple()
    #     self.fields["participants"].queryset = VogonUser.objects.order_by('username')


class MySplitDateTimeWidget(forms.widgets.SplitDateTimeWidget):
    """
    Allow addition of separate CSS classes for the Date and Time widgets.
    """
    def __init__(self, attrs=None, date_format=None, time_format=None):
        date_class = attrs.get('date_class', '')
        date_placeholder = attrs.get('date_placeholder', '')
        if date_class:
            del attrs['date_class']
        if date_placeholder:
            del attrs['date_placeholder']

        time_class = attrs.get('time_class', '')
        time_placeholder = attrs.get('time_placeholder', '')
        if time_class:
            del attrs['time_class']
        if time_placeholder:
            del attrs['time_placeholder']

        widgets = (forms.widgets.DateInput(attrs={'class' : date_class, 'placeholder': date_placeholder}, format=date_format),
                   forms.widgets.TimeInput(attrs={'class' : time_class, 'placeholder': time_placeholder}, format=time_format))
        super(forms.widgets.SplitDateTimeWidget, self).__init__(widgets, attrs)





class RepositorySearchForm(forms.Form):
    query = forms.CharField(max_length=255, widget=widgets.TextInput(attrs={'class': 'form-control'}))
