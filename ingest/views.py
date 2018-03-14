from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.

def index(request):
    return HttpResponse("Hello, world.")

def detail(request, metadata_id):
    return HttpResponse("You're looking at metadata %s." % metadata_id)
