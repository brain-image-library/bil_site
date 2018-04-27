from django.contrib import admin

from .models import MinimalImgMetadata
from .models import Collection

admin.site.register(MinimalImgMetadata)
admin.site.register(Collection)
