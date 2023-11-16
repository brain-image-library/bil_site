from calendar import c
from xmlrpc.client import Boolean
from django.conf import settings
from django.contrib import messages, auth
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import FileSystemStorage
from django.shortcuts import render, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import DetailView
from django.views.generic.edit import UpdateView, DeleteView
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse, Http404

from django_filters.views import FilterView
from django_tables2.views import SingleTableMixin
from django_tables2 import RequestConfig
import pyexcel as pe
import xlrd
import re
import configparser

from celery.result import AsyncResult

from .. import tasks
from ..mne import Mne
from ..field_list import required_metadata
from ..filters import CollectionFilter
from ..forms import CollectionForm, ImageMetadataForm, DescriptiveMetadataForm, UploadForm, collection_send
from ..models import UUID, Collection, ImageMetadata, DescriptiveMetadata, Project, ProjectPeople, People, Project, EventsLog, Contributor, Funder, Publication, Instrument, Dataset, Specimen, Image, Sheet, Consortium, ProjectConsortium, SWC, ProjectAssociation
from ..tables import CollectionTable, DescriptiveMetadataTable, CollectionRequestTable
import uuid
import datetime
import json
from datetime import datetime

config = configparser.ConfigParser()
config.read('site.cfg')

# this function presents all users for changing of PI and PO
@login_required
def modify_user(request, pk):
    current_user = request.user
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False
    person = People.objects.get(auth_user_id_id = pk)
    
    all_project_people = ProjectPeople.objects.filter(people_id_id=person.id).all()   
    for project_person in all_project_people:
        try:
            their_project = Project.objects.get(id=project_person.project_id_id)
        except Project.DoesNotExist:
            their_project = None
            return render(request, 'ingest/no_projects.html', {'pi':pi})
        project_person.their_project = their_project
    return render(request, 'ingest/modify_user.html', {'all_project_people':all_project_people, 'person':person})    

# this function presents all users and gives a bil admin the option to add or remove bil admin privs to said users
@login_required
def modify_biladmin_privs(request, pk):
    # use pk to find the user in the people table
    person = People.objects.get(auth_user_id_id = pk)
    return render(request, 'ingest/modify_biladmin_privs.html', {'person':person})

# this function does the actual changing of bil admin privs
@login_required
def change_bil_admin_privs(request):
    content = json.loads(request.body)
    items = []
    for item in content:
        items.append(item['is_bil_admin'])
        is_bil_admin = item['is_bil_admin']
        person_id = item['person_id']
        
        person = People.objects.get(id=person_id)
        person.is_bil_admin=is_bil_admin
        person.save()
    return HttpResponse(json.dumps({'url': reverse('ingest:index')}))

