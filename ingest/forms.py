from django import forms
from .field_list import metadata_fields, collection_fields
from .models import ImageMetadata, DescriptiveMetadata, Collection, DatasetLinkage
from django.utils import timezone



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

    class Meta:
        model = Collection
        fields = collection_fields
        widgets = {
            'project': forms.TextInput(attrs={'list': 'project_list'}),
            
            'project_funder_id': forms.TextInput(attrs={'list': 'funder_list'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        return super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        kwargs['commit'] = False
        obj = super().save(*args, **kwargs)
        if self.request:
            obj.user = self.request.user
        obj.save()
        return obj

class CollectionChoice(forms.Form):
    collection = forms.ModelChoiceField(
        queryset=None,  
        empty_label=None,  
        widget=forms.Select(attrs={'class': 'collection-select'})  # Add class for Select2
    )

    def __init__(self, user, *args, **kwargs):
        super(CollectionChoice, self).__init__(*args, **kwargs)
        self.fields['collection'].queryset = Collection.objects.filter(user=user)

    def label_from_instance(self, obj):
        return f"{obj.name} ({obj.bil_uuid})"  # Display both name and BIL UUID in the dropdown

class DatasetLinkageForm(forms.ModelForm):
    class Meta:
        model = DatasetLinkage
        fields = ['code_id', 'data_id_2', 'relationship', 'description']
        widgets = {
            'code_id': forms.Select(attrs={'class': 'form-control'}),
            'data_id_2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Data ID 2'}),
            'relationship': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Add a description'}),
        }

    def save(self, commit=True, *args, **kwargs):
        instance = super().save(commit=False)
        # Automatically set the linkage_date to now
        instance.linkage_date = timezone.now().date()
        if commit:
            instance.save()
        return instance