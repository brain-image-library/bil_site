from django import forms
from .field_list import metadata_fields, collection_fields
from .models import ImageMetadata, DescriptiveMetadata, Collection


class UploadForm(forms.Form):
    associated_collection = forms.ModelChoiceField(queryset=Collection.objects.all())

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
