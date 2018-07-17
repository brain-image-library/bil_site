from django.contrib import admin

from .models import ImageMetadata
from .models import Collection

admin.site.register(ImageMetadata)
admin.site.register(Collection)
