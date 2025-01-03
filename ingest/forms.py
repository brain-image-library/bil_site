from django import forms
from .field_list import metadata_fields, collection_fields
from .models import ImageMetadata, DescriptiveMetadata, Collection, Project


class UploadForm(forms.Form):
    associated_submission = forms.ModelChoiceField(queryset=Collection.objects.all())

class DescriptiveMetadataForm(forms.ModelForm):

    class Meta:
        model = ImageMetadata
        fields = metadata_fields

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')  # To get request.user. Do not use kwargs.pop('user', None) due to potential security hole
        super().__init__(*args, **kwargs)
        self.fields['submission'].queryset = Collection.objects.filter(
            locked=False, user=self.user)

    def save(self, *args, **kwargs):
        kwargs['commit'] = False
        obj = super().save(*args, **kwargs)
        if self.user:
            obj.user = self.user
        obj.save()
        return obj

class ImageMetadataForm(forms.ModelForm):
    age = forms.IntegerField(min_value=0)

    class Meta:
        model = ImageMetadata
        fields = metadata_fields

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')  # To get request.user. Do not use kwargs.pop('user', None) due to potential security hole
        super().__init__(*args, **kwargs)
        self.fields['collection'].queryset = Collection.objects.filter(
            locked=False, user=self.user)

    def save(self, *args, **kwargs):
        kwargs['commit'] = False
        obj = super().save(*args, **kwargs)
        if self.user:
            obj.user = self.user
        obj.save()
        return obj

class collection_send(forms.ModelForm):
    class Meta:
        model = Collection
        fields = collection_fields
        

class CollectionForm(forms.ModelForm):
    project = forms.ModelChoiceField(
        queryset=Project.objects.none(),  # Default to an empty queryset
        widget=forms.Select,  # Dropdown widget
        required=True,
        label="Project",
    )

    class Meta:
        model = Collection
        fields = collection_fields
        widgets = {
            'project_funder_id': forms.TextInput(attrs={'list': 'funder_list'}),
        }

    def __init__(self, *args, **kwargs):
        # Accept and process additional arguments
        project_queryset = kwargs.pop('project_queryset', None)
        self.request = kwargs.pop('request', None)  # Track the request object for user
        super().__init__(*args, **kwargs)

        # Set the queryset for the project field dynamically
        if project_queryset:
            self.fields['project'].queryset = project_queryset

    def save(self, *args, **kwargs):
        # Ensure commit is False to attach the user
        kwargs['commit'] = False
        obj = super().save(*args, **kwargs)
        if self.request:
            obj.user = self.request.user  # Attach the current user to the object
        obj.save()
        return obj
class CollectionChoice(forms.Form):
    collection = forms.ModelChoiceField(
        queryset=None,  # We'll set this dynamically in the view
        empty_label=None  # Ensures user must select a collection
    )

    def __init__(self, user, *args, **kwargs):
        super(CollectionChoice, self).__init__(*args, **kwargs)
        # Dynamically filter queryset based on the logged-in user
        self.fields['collection'].queryset = Collection.objects.filter(user=user)