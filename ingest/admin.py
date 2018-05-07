from django.contrib import admin

from .models import ImageData
from .models import ImageMetadata
from .models import Collection

admin.site.register(ImageData)
admin.site.register(ImageMetadata)
admin.site.register(Collection)
