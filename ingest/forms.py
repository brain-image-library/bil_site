from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .fieldlist import attrs
from .models import ImageMetadata
from .models import Collection


class UploadForm(forms.Form):
    associated_collection = forms.ModelChoiceField(queryset=Collection.objects.all())


class ImageMetadataForm(forms.ModelForm):

    class Meta:
        model = ImageMetadata
        fields = attrs

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


class CollectionForm(forms.ModelForm):

    class Meta:
        model = Collection
        fields = (
            'name',
            'description',
            'organization_name',
            'lab_name',
            'project_funder',
            'project_funder_id')

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
