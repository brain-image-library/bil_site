from django.http import HttpResponse
from django.template import loader
from django.shortcuts import get_object_or_404, render

from .models import MinimalImgMetadata


def index(request):
    latest_metadata_list = MinimalImgMetadata.objects.order_by('-organization_name')[:5]
    context = {'latest_metadata_list': latest_metadata_list}
    return render(request, 'ingest/index.html', context)

def detail(request, metadata_id):
    metadata = get_object_or_404(MinimalImgMetadata, pk=metadata_id)
    return render(request, 'ingest/detail.html', {'metadata': metadata})
