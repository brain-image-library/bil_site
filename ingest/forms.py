from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import ImageMetadata
from .models import Collection

class SignUpForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, help_text='Required')
    last_name = forms.CharField(max_length=30, help_text='Required')
    email = forms.EmailField(max_length=254, help_text='Required. A valid email address.')

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2', )

class ImageMetadataForm(forms.ModelForm):

    class Meta:
        model = ImageMetadata
        fields = (
            'project_name',
            'organization_name',
            'project_description',
            'project_funder_id',
            'background_strain',
            'image_filename_pattern')

class CollectionForm(forms.ModelForm):

    class Meta:
        model = Collection
        fields = (
            'name',
            'description',
            'metadata',
            'data_path')
