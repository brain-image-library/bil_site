from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic
from django.shortcuts import redirect

from .models import MinimalImgMetadata
from .forms import MIMForm


class IndexView(generic.ListView):
    template_name = 'ingest/index.html'
    context_object_name = 'latest_metadata_list'

    def get_queryset(self):
        """Return the last five published metadata."""
        return MinimalImgMetadata.objects.order_by('-organization_name')[:5]


class DetailView(generic.DetailView):
    model = MinimalImgMetadata
    template_name = 'ingest/detail.html'
    context_object_name = 'metadata'


def post_new(request):
    if request.method == "POST":
        form = MIMForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            # post.author = request.user
            # post.published_date = timezone.now()
            post.save()
            # return redirect('post_detail', pk=post.pk)
    else:
        form = MIMForm()
    return render(request, 'ingest/post_edit.html', {'form': form})
