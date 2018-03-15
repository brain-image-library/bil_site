from django import forms

from .models import MinimalImgMetadata

class MIMForm(forms.ModelForm):

    class Meta:
        model = MinimalImgMetadata
        fields = (
            'project_name',
            'organization_name',
            'project_description',
            'submitter_email')
