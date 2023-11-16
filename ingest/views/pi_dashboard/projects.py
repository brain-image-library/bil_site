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
from ...mne import Mne
from ...field_list import required_metadata
from ...filters import CollectionFilter
from ...forms import CollectionForm, ImageMetadataForm, DescriptiveMetadataForm, UploadForm, collection_send
from ...models import UUID, Collection, ImageMetadata, DescriptiveMetadata, Project, ProjectPeople, People, Project, EventsLog, Contributor, Funder, Publication, Instrument, Dataset, Specimen, Image, Sheet, Consortium, ProjectConsortium, SWC, ProjectAssociation
from ...tables import CollectionTable, DescriptiveMetadataTable, CollectionRequestTable
import uuid
import datetime
import json
from datetime import datetime

config = configparser.ConfigParser()
config.read('site.cfg')


# this function lists all the users so a pi can assign people to their project
@login_required
def list_all_users(request):
    current_user = request.user
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False
    allusers = User.objects.all()
    return render(request, 'ingest/list_all_users.html', {'allusers':allusers, 'pi':pi})

@login_required
def manageProjects(request):
    current_user = request.user
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id, is_pi = True).all()
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False
    
    allprojects=[]
    for row in project_person:
        project_id = row.project_id_id
        project =  Project.objects.get(id=project_id)
        allprojects.append(project)

        project_consortia = ProjectConsortium.objects.filter(project_id=project.id).all()
        project.short_names = []
        for c in project_consortia:
            short_name = Consortium.objects.get(id=c.consortium_id).short_name
            project.short_names.append(short_name)
        project.short_names = ', '.join(project.short_names)
        
        proj_assocs = ProjectAssociation.objects.filter(project_id=project.id).all()
        parent_proj_assocs = ProjectAssociation.objects.filter(parent_project_id=project.id).all()

        project.parent_project_names = []
        for p in proj_assocs:
            parent_project_name = Project.objects.get(id=p.parent_project_id).name
            project.parent_project_names.append(parent_project_name)
        project.parent_project_names = ', '.join(project.parent_project_names)

        project.child_project_names = []
        for pa in parent_proj_assocs:
            child_project_name = Project.objects.get(id=pa.project_id).name
            project.child_project_names.append(child_project_name)
        project.child_project_names = ', '.join(project.child_project_names)

    return render(request, 'ingest/manage_projects.html', {'allprojects':allprojects, 'pi':pi})

# add a new project
@login_required
def project_form(request):
    current_user = request.user
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    allprojects=[]
    for row in project_person:
        project_id = row.project_id_id
        project =  Project.objects.get(id=project_id)
        allprojects.append(project)    
        
    consortia = Consortium.objects.all
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False
    return render(request, 'ingest/project_form.html', {'pi':pi, 'allprojects':allprojects, 'consortia':consortia})

# takes the data from project_form
@login_required
def create_project(request):
    new_project = json.loads(request.body)
    print(new_project)
    items = []
    for item in new_project:
        items.append(item['funded_by'])
        items.append(item['name'])
        items.append(item['consortia_ids'])
        items.append(item['parent_project'])

        funded_by = item['funded_by']
        name = item['name']
        consortia_ids = item['consortia_ids']
        parent_project = item['parent_project']

        # write project to the project table   
        project = Project(funded_by=funded_by, name=name)
        project.save()

        proj_id = project.id

        for c in consortia_ids:
          project_consortium = ProjectConsortium(project_id=proj_id, consortium_id=c)
          project_consortium.save()

        if parent_project:
            project_association = ProjectAssociation(project_id=proj_id, parent_project_id=int(parent_project))
            project_association.save()

        
        # create a project_people row for this pi so they can view project on pi dashboard
        project_id_id = project.id
        current_user = request.user
        person = People.objects.get(auth_user_id_id=current_user)
        
        project_person = ProjectPeople(project_id_id=project_id_id, people_id_id=person.id, is_pi=True, is_po=False, doi_role='creator')
        project_person.save()
    messages.success(request, 'Project Created!')    
    return HttpResponse(json.dumps({'url': reverse('ingest:manage_projects')}))

@login_required
def add_project_user(request, pk):
    current_user = request.user
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False
    all_users = User.objects.all()
    project = Project.objects.get(id=pk) 
    return render(request, 'ingest/add_project_user.html', {'all_users':all_users, 'project':project, 'pi':pi})


# adds person to a project
@login_required
def write_user_to_project_people(request):
    content = json.loads(request.body)
    items = []
    for item in content:
        items.append(item['user_id'])
        items.append(item['project_id'])
        user_id = item['user_id']
        project_id = item['project_id']

        project = Project.objects.get(id=project_id) 
        person = People.objects.get(auth_user_id_id=user_id)
        project_person = ProjectPeople(project_id_id=project.id, people_id_id=person.id, is_pi=False, is_po=False, doi_role='')
        
        try:
            check =  ProjectPeople.objects.get(project_id_id=project.id, people_id_id=person.id)
            user = User.objects.get(id=user_id)
        except:
            project_person.save()
    messages.success(request, 'User(s) Added!')
    return HttpResponse(json.dumps({'url': reverse('ingest:manage_projects')}))

# presents all people on the projects of the pi who is logged in
@login_required
def people_of_pi(request):
    current_user = request.user
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False
    
    pi = People.objects.get(auth_user_id_id=current_user.id)
    # filters the project_people table down to the rows where it's the pi's people_id_id AND is_pi=true
    pi_projects = ProjectPeople.objects.filter(people_id_id=pi.id, is_pi=True).all()
    for proj in pi_projects:
        proj.related_project_people = ProjectPeople.objects.filter(project_id=proj.project_id_id).all()
    return render(request, 'ingest/people_of_pi.html', {'pi_projects':pi_projects, 'pi':pi})

@login_required
def view_project_people(request, pk):
    current_user = request.user
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False
    try:
        project = Project.objects.get(id=pk)
        # get all of the project people rows with the project_id matching the project.id
        projectpeople = ProjectPeople.objects.filter(project_id_id=pk).all()
        # get all of the people who are in those projectpeople rows
        allpeople = []
        for row in projectpeople:
            person_id = row.people_id_id
            person = People.objects.get(id=person_id)
            allpeople.append(person)
        return render(request, 'ingest/view_project_people.html', { 'project':project, 'allpeople':allpeople })
    except ProjectPeople.DoesNotExist:
        return render(request, 'ingest/no_people.html')
    return render(request, 'ingest/view_project_people.html', {'allpeople':allpeople, 'project':project, 'pi':pi})

# fallback for when a project has no collections associated with it
@login_required
def no_collection(request, pk):
    current_user = request.user
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False
    project = Project.objects.get(id=pk)
    return(request, 'ingest/no_collection.html',  {'project':project, 'pi':pi})

# fallback for when a project has no people assigned to it
@login_required
def no_people(request, pk):
    current_user = request.user
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False
    project = Project.objects.get(id=pk)
    return(request, 'ingest/no_people.html', {'project':project, 'pi':pi})

# view all the collections of a project
@login_required
def view_project_collections(request, pk):
    current_user = request.user
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False
    try:
        project = Project.objects.get(id=pk)
        project_collections = Collection.objects.filter(project_id=project.id).all()
        
        for collection in project_collections:
            user_id = collection.user_id
            owner = User.objects.get(id=user_id)
            try:
                event = EventsLog.objects.filter(collection_id_id=collection.id).latest('event_type')
            except EventsLog.DoesNotExist:
                event = None
            collection.event = event
            collection.owner = owner
       
    except Collection.DoesNotExist:
        return render(request, 'ingest/no_collection.html')  
    return render(request, 'ingest/view_project_collections.html', {'project':project, 'project_collections':project_collections, 'pi':pi})