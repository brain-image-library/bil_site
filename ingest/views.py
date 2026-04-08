from calendar import c
from xmlrpc.client import Boolean
from django.conf import settings
from django.contrib import messages, auth
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import FileSystemStorage
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import DetailView
from django.views.generic.edit import UpdateView, DeleteView
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse, Http404, HttpResponseRedirect

from django_filters.views import FilterView
from django_tables2.views import SingleTableMixin
from django_tables2 import RequestConfig
import pyexcel as pe
import xlrd
import re
import io
import pandas as pd
from celery.result import AsyncResult

from . import tasks
from .mne import Mne
from .specimen_portal import Specimen_Portal
from .field_list import required_metadata
from .filters import CollectionFilter
from .forms import CollectionForm, ImageMetadataForm, DescriptiveMetadataForm, UploadForm, collection_send, CollectionChoice, DatasetLinkageForm
from .models import UUID, Collection, ImageMetadata, DescriptiveMetadata, Project, ProjectPeople, People, Project, EventsLog, Contributor, Funder, Publication, Instrument, Dataset, Specimen, Image, Sheet, Consortium, ProjectConsortium, SWC, ProjectAssociation, BIL_ID, DatasetEventsLog, BIL_Specimen_ID, BIL_Instrument_ID, BIL_Project_ID, SpecimenLinkage, DatasetTag, ConsortiumTag, DatasetLinkage, Spatial
from .tables import CollectionTable, DescriptiveMetadataTable, CollectionRequestTable
import uuid
import datetime
import json
from datetime import datetime
import os
from django.middleware.csrf import get_token
import requests
from django.utils.timezone import now
from django.utils import timezone
from django.db import transaction

from django.db.models import OuterRef, Subquery, Q, Exists, Count, F, Sum
from django.db.models.functions import ExtractYear
from pathlib import Path
import jwt, time
import brainimagelibrary


def _get_public_dataset_stats():
    """Return (public_dataset_count, public_file_count, datasets_by_year).

    All stats come from brainimagelibrary.summary.daily() (dict response).
    Falls back to local ORM if the SDK call fails.
    Results are cached for 1 hour.
    """
    cached = cache.get('public_dataset_stats')
    if cached is not None:
        return cached

    # --- Per-year breakdown from ORM (always, for the bar chart) ---
    _latest_sheet_subq = Subquery(
        Sheet.objects.filter(
            collection_id=OuterRef('collection_id'),
        ).order_by('-date_uploaded').values('id')[:1]
    )
    latest_sheet_ids = (
        Sheet.objects
        .filter(collection__submission_status='SUCCESS',
                collection__validation_status='SUCCESS')
        .annotate(latest_id=_latest_sheet_subq)
        .filter(latest_id=F('id'))
        .values_list('id', flat=True)
    )
    upgraded_v1_ids = BIL_ID.objects.filter(
        v1_ds_id__isnull=False, v2_ds_id__isnull=False,
    ).values_list('v1_ds_id', flat=True)
    v2_by_year = (
        Dataset.objects.filter(sheet_id__in=latest_sheet_ids)
        .annotate(year=ExtractYear('sheet__date_uploaded'))
        .values('year').annotate(n=Count('id')).order_by('year')
    )
    v1_by_year = (
        DescriptiveMetadata.objects
        .filter(collection__submission_status='SUCCESS',
                collection__validation_status='SUCCESS')
        .exclude(id__in=upgraded_v1_ids)
        .annotate(year=ExtractYear('date_created'))
        .values('year').annotate(n=Count('id')).order_by('year')
    )
    year_map = {}
    for row in v2_by_year:
        if row['year']:
            year_map[row['year']] = year_map.get(row['year'], 0) + row['n']
    for row in v1_by_year:
        if row['year']:
            year_map[row['year']] = year_map.get(row['year'], 0) + row['n']
    datasets_by_year = [{'year': y, 'count': year_map[y]} for y in sorted(year_map)]

    # --- Dataset count + file count from SDK ---
    try:
        data = brainimagelibrary.summary.daily()
        if data and isinstance(data, dict):
            public_dataset_count = int(data.get('number_of_datasets', 0))
            public_file_count = int(data.get('number_of_files', 0))
            result = (public_dataset_count, public_file_count, datasets_by_year)
            cache.set('public_dataset_stats', result, 3600)
            return result
    except Exception:
        pass

    # --- ORM fallback for dataset count + file count ---
    public_file_count = (
        Dataset.objects
        .filter(sheet_id__in=latest_sheet_ids, number_of_files__isnull=False)
        .aggregate(total=Sum('number_of_files'))['total'] or 0
    )
    v2_count = Dataset.objects.filter(sheet_id__in=latest_sheet_ids).count()
    v1_count = DescriptiveMetadata.objects.filter(
        collection__submission_status='SUCCESS',
        collection__validation_status='SUCCESS',
    ).exclude(id__in=upgraded_v1_ids).count()
    public_dataset_count = v2_count + v1_count
    return (public_dataset_count, public_file_count, datasets_by_year)


def logout(request):
    messages.success(request, "You've successfully logged out")
    # XXX: this view should be separated from the the ingestion views and
    # placed with other authentication views to allow us to reuse the
    # authentication views with other apps (e.g. data exploration portal).
    auth.logout(request)
    # Send the user back to the login page when they log out.
    # XXX: we might want to use django's messaging system to inform them that
    # they've successfully logged out.
    return redirect('login')

def signup(request):
    """ Info about signing up for a new account. """
    # XXX: this view should be separated from the the ingestion views and
    # placed with other authentication views to allow us to reuse the
    # authentication views with other apps (e.g. data exploration portal).
    return render(request, 'ingest/signup.html')

@login_required
def index(request):
    """ The main/home page. """
    current_user = request.user

    # --- Step 1: Ensure People and ProjectPerson exist ---
    try:
        people = People.objects.get(auth_user_id_id=current_user.id)
        project_person = ProjectPeople.objects.filter(people_id=people.id).all()
    except ObjectDoesNotExist:
        people = People()
        people.name = current_user.username
        people.orcid = ''
        people.affiliation = ''
        people.affiliation_identifier = ''
        people.is_bil_admin = False
        people.auth_user_id = current_user
        people.save()

        project = Project()
        pname = current_user.username + ' Project 1'
        project.name = pname
        project.funded_by = ''
        project.is_biccn = False
        project.save()

        save_project_id(project)

        project_people = ProjectPeople()
        project_people.project_id = project
        project_people.people_id = people
        project_people.is_pi = False
        project_people.is_po = False
        project_people.save()

    # --- Step 2: Ensure user-specific Consortium exists ---
    user_consortium_short_name = f"user_{current_user.username}"
    Consortium.objects.get_or_create(
        short_name=user_consortium_short_name,
        defaults={"long_name": f"User Tags for {current_user.username}"}
    )

    # --- Step 3: Routing logic based on role ---
    public_dataset_count, public_file_count, datasets_by_year = _get_public_dataset_stats()

    try:
        people = People.objects.get(auth_user_id_id=current_user.id)
        project_person = ProjectPeople.objects.filter(people_id=people.id).all()
        if people.is_bil_admin:
            return render(request, 'ingest/bil_index.html', {
                'people': people,
                'public_dataset_count': public_dataset_count,
                'public_file_count': public_file_count,
                'datasets_by_year': datasets_by_year,
            })
        for attribute in project_person:
            if attribute.is_pi:
                return render(request, 'ingest/pi_index.html', {
                    'project_person': attribute,
                    'public_dataset_count': public_dataset_count,
                    'public_file_count': public_file_count,
                    'datasets_by_year': datasets_by_year,
                })
    except Exception as e:
        print(e)

    return render(request, 'ingest/index.html', {
        'public_dataset_count': public_dataset_count,
        'public_file_count': public_file_count,
        'datasets_by_year': datasets_by_year,
    })


@login_required
def pi_index(request):
    current_user = request.user
    try:
        people = People.objects.get(auth_user_id_id = current_user.id)
        project_person = ProjectPeople.objects.filter(people_id = people.id).all()
        
        for attribute in project_person:
            if project_person.is_pi:
                return render(request, 'ingest/pi_index.html', {'project_person': attribute})
    except Exception as e:
        print(e)
    return render(request, 'ingest/index.html')

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

# this function does the actual changing of is_pi or is_po of users
@login_required
def userModify(request):
    content = json.loads(request.body)
    items = []
    for item in content:
        items.append(item['is_pi'])
        items.append(item['is_po'])
        items.append(item['auth_id'])
        items.append(item['project_id'])
        is_pi = item['is_pi']
        is_po = item['is_po']
        auth_id = item['auth_id']
        project_id = item['project_id']
        
        project_person = ProjectPeople.objects.get(id=project_id)
        project_person.is_pi=is_pi
        project_person.is_po=is_po
        project_person.save()
        
    return HttpResponse(json.dumps({'url': reverse('ingest:index')}))

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

        project.parent_ids = [p.parent_project_id for p in proj_assocs]
        project.is_child = bool(project.parent_ids)

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

    # Recursively sort so children of children are placed correctly at any depth
    placed = set()
    sorted_projects = []

    def place_project(p, level):
        if p.id in placed:
            return
        placed.add(p.id)
        p.indent_level = level
        p.td_padding = f'{level * 1.5 + 0.5}rem' if level > 0 else ''
        p.connector_left = f'{(level - 1) * 1.5 + 0.75}rem' if level > 0 else ''
        sorted_projects.append(p)
        for child in allprojects:
            if child.id not in placed and p.id in child.parent_ids:
                place_project(child, level + 1)

    for p in allprojects:
        if not p.is_child:
            place_project(p, 0)
    for p in allprojects:
        if p.id not in placed:
            place_project(p, 1)

    return render(request, 'ingest/manage_projects.html', {'allprojects': sorted_projects, 'pi': pi})

# this functions allows pi to see all the collections
@login_required
def manageCollections(request):
    current_user = request.user
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False
    # gathers all the collections associated with the PI, linked on pi_index.html
    collections = []
    allprojects = ProjectPeople.objects.filter(people_id_id=people.id, is_pi=True).all()
    for proj in allprojects:
        project = Project.objects.get(id = proj.project_id_id)
        collection = Collection.objects.filter(project_id=project.id).all()
        collections.extend(collection)
    return render(request, 'ingest/manage_collections.html', {'pi':pi, 'collections':collections})

# add a new project
@login_required
def project_form(request):
    current_user = request.user
    people = People.objects.get(auth_user_id_id=current_user.id)
    project_person = ProjectPeople.objects.filter(people_id=people.id)

    allprojects = []
    for row in project_person:
        project = Project.objects.get(id=row.project_id_id)
        allprojects.append(project)

    # Filter out user-specific consortia (e.g., user_luketuite)
    consortia = Consortium.objects.exclude(short_name__startswith='user_')

    # Determine PI status
    pi = any(attribute.is_pi for attribute in project_person)

    return render(request, 'ingest/project_form.html', {
        'pi': pi,
        'allprojects': allprojects,
        'consortia': consortia,
    })

# takes the data from project_form
@login_required
def create_project(request):
    new_project = json.loads(request.body)
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
        save_project_id(project)
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
    people = People.objects.get(auth_user_id_id=current_user.id)
    project_person = ProjectPeople.objects.filter(people_id=people.id).all()
    pi = any(attr.is_pi for attr in project_person)
    project = Project.objects.get(id=pk)
    existing = ProjectPeople.objects.filter(project_id_id=pk).select_related('people_id')
    members = []
    for ep in existing:
        if ep.people_id and ep.people_id.auth_user_id:
            members.append(ep.people_id.auth_user_id)
    return render(request, 'ingest/add_project_user.html', {'project': project, 'pi': pi, 'members': members})

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


@login_required
def add_user_by_username(request):
    if request.method != 'POST':
        return HttpResponse(status=405)
    data = json.loads(request.body)
    username = data.get('username', '').strip()
    project_id = data.get('project_id')
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return HttpResponse(json.dumps({'success': False, 'message': f'No user found with username "{username}". They may not have logged into the portal yet.'}), content_type='application/json')
    try:
        person = People.objects.get(auth_user_id_id=user.id)
    except People.DoesNotExist:
        return HttpResponse(json.dumps({'success': False, 'message': f'User "{username}" has not set up a profile in the portal yet.'}), content_type='application/json')
    project = Project.objects.get(id=project_id)
    if ProjectPeople.objects.filter(project_id_id=project.id, people_id_id=person.id).exists():
        return HttpResponse(json.dumps({'success': False, 'message': f'"{username}" is already a member of this project.'}), content_type='application/json')
    ProjectPeople(project_id_id=project.id, people_id_id=person.id, is_pi=False, is_po=False, doi_role='').save()
    return HttpResponse(json.dumps({'success': True, 'message': f'"{username}" has been added to the project.', 'username': username}), content_type='application/json')


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
    pi_projects = list(ProjectPeople.objects.filter(people_id_id=pi.id, is_pi=True).all())
    for proj in pi_projects:
        proj.related_project_people = ProjectPeople.objects.filter(project_id=proj.project_id_id).all()
        proj_assocs = ProjectAssociation.objects.filter(project_id=proj.project_id_id).all()
        proj.parent_ids = [p.parent_project_id for p in proj_assocs]
        proj.is_child = bool(proj.parent_ids)

    # Recursively sort so children of children are placed correctly at any depth
    placed = set()
    sorted_projs = []

    def place_proj(proj, level):
        if proj.project_id_id in placed:
            return
        placed.add(proj.project_id_id)
        proj.indent_level = level
        proj.card_margin = f'{level * 2}rem' if level > 0 else '0'
        sorted_projs.append(proj)
        for child in pi_projects:
            if child.project_id_id not in placed and proj.project_id_id in child.parent_ids:
                place_proj(child, level + 1)

    for proj in pi_projects:
        if not proj.is_child:
            place_proj(proj, 0)
    for proj in pi_projects:
        if proj.project_id_id not in placed:
            place_proj(proj, 1)

    return render(request, 'ingest/people_of_pi.html', {'pi_projects': sorted_projs, 'pi': pi})


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
        projectpeople = ProjectPeople.objects.filter(project_id_id=pk).select_related('people_id', 'people_id__auth_user_id').all()
        members = []
        for row in projectpeople:
            person = row.people_id
            if person:
                members.append({
                    'name': person.name,
                    'username': person.auth_user_id.username if person.auth_user_id else '—',
                    'affiliation': person.affiliation,
                    'is_pi': row.is_pi,
                    'is_po': row.is_po,
                })
        return render(request, 'ingest/view_project_people.html', {'project': project, 'members': members})
    except ProjectPeople.DoesNotExist:
        return render(request, 'ingest/no_people.html')

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

@login_required
def descriptive_metadata_list(request):
    current_user = request.user
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False
    """ A list of all the metadata the user has created. """
    # The user is trying to delete the selected metadata
    for key in request.POST:
        messages.success(request, key) 
        messages.success(request, request.POST[key])
    if request.method == "POST":
        pks = request.POST.getlist("selection")
        # Get all of the checked metadata (except LOCKED metadata)
        selected_objects = DescriptiveMetadata.objects.filter(
            pk__in=pks, locked=False)
        selected_objects.delete()
        messages.success(request, 'Descriptive Metadata successfully deleted')
        return redirect('ingest:descriptive_metadata_list')
    # This is the GET (just show the user their list of metadata)
    else:
        # XXX: This exclude is likely redundant, becaue there's already the
        # same exclude in the class itself. Need to test though.
        table = DescriptiveMetadataTable(
            DescriptiveMetadata.objects.filter(user=request.user), exclude=['user'])
        RequestConfig(request).configure(table)
        descriptive_metadata = DescriptiveMetadata.objects.filter(user=request.user).last()
    
        datasets_list = []
        collections = Collection.objects.filter(user=request.user)
        for c in collections:
            sheets = Sheet.objects.filter(collection_id=c.id).last()
            #for s in sheets:
            if sheets != None:
                datasets = Dataset.objects.filter(sheet_id=sheets.id)
                for d in datasets:
                    datasets_list.append(d)

        return render(
            request,
            'ingest/descriptive_metadata_list.html',
            {'table': table, 'descriptive_metadata': descriptive_metadata, 'pi':pi, 'datasets_list':datasets_list})

def new_metadata_detail(request, pk):
    contributors = Contributor.objects.filter(sheet_id=pk).all()
    funders = Funder.objects.filter(sheet_id=pk).all 
    publications = Publication.objects.filter(sheet_id=pk).all()
    instruments = Instrument.objects.filter(sheet_id=pk).all()
    datasets = Dataset.objects.filter(sheet_id=pk).all()
    specimens = Specimen.objects.filter(sheet_id=pk).all()
    images = Image.objects.filter(sheet_id=pk).all()
    swcs = SWC.objects.filter(sheet_id=pk).all()
    
    return render(request, 'ingest/new_metadata_detail.html', {'contributors':contributors, 'funders':funders, 'publications':publications, 'instruments':instruments, 'datasets':datasets, 'specimens':specimens, 'images':images, 'swcs':swcs})

class DescriptiveMetadataDetail(LoginRequiredMixin, DetailView):
    """ A detailed view of a single piece of metadata. """
    model = DescriptiveMetadata
    template_name = 'ingest/descriptive_metadata_detail.html'
    context_object_name = 'descriptive_metadata'

@login_required
def collection_send(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        payload = json.loads(request.body or "[]")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    # Normalize to list of bil_uuids
    bil_uuids = []
    for item in payload:
        if isinstance(item, dict) and "bil_uuid" in item:
            bil_uuids.append(item["bil_uuid"])
        elif isinstance(item, str):
            bil_uuids.append(item)
    bil_uuids = list(dict.fromkeys(bil_uuids))

    sent = []
    skipped = {
        "missing_metadata": [],
        "already_requested": [],
        "already_success": [],
        "not_found": [],
    }
    curation_issues = {}

    user = request.user
    user_email = getattr(user, "email", "") or f"{user.username}@psc.edu"

    valid_for_validation = []

    # --- Iterate through each selected submission ---
    for bu in bil_uuids:
        try:
            coll = Collection.objects.get(bil_uuid=bu, user=user)
        except Collection.DoesNotExist:
            skipped["not_found"].append(
                {"uuid": bu, "reason": "No submission found for this user."}
            )
            continue

        if (
            coll.submission_status == Collection.SUCCESS
            and coll.validation_status == Collection.SUCCESS
        ):
            skipped["already_success"].append(
                {"uuid": bu, "reason": "This submission has already been validated."}
            )
            continue

        has_sheet = Sheet.objects.filter(collection=coll).exists()
        if not has_sheet:
            skipped["missing_metadata"].append(
                {"uuid": bu, "reason": "No metadata spreadsheet uploaded yet."}
            )
            continue

        already_req = EventsLog.objects.filter(
            collection_id=coll, event_type="request_validation"
        ).exists()
        if already_req:
            skipped["already_requested"].append(
                {"uuid": bu, "reason": "Validation already requested for this collection."}
            )
            continue

        # --- Run pre-curation directory check BEFORE logging event ---
        curation_result = check_collection_directories(coll, user)
        if curation_result["status"] != "ok":
            # Store issue per collection
            curation_issues[bu] = curation_result
            continue

        valid_for_validation.append(coll)

    # --- Proceed only with valid submissions ---
    for coll in valid_for_validation:
        try:
            person = People.objects.get(auth_user_id_id=user.id)
            EventsLog.objects.create(
                collection_id=coll, 
                people_id_id=person.id,
                project_id_id=coll.project_id,
                timestamp=timezone.now(),
                event_type="request_validation",
            )
        except People.DoesNotExist:
            EventsLog.objects.create(
                collection_id=coll, 
                project_id_id=coll.project_id,
                notes="(No People record found for user)",
                timestamp=timezone.now(),
                event_type="request_validation",
            )

        sent.append(coll.bil_uuid)

    # --- Send email & Asana task only for successfully sent ones ---
    if sent:
        subject = "[BIL Validations] New Validation Request"
        sender = "noreply@psc.edu"
        recipient = ["ltuite96@psc.edu"]
        message = (
            f"The following collections have been requested for validation by {user_email}:\n\n"
            + "\n".join(f"• {uuid}" for uuid in sent)
        )
        send_mail(subject, message, sender, recipient)
        try:
            _create_asana_tasks(sent, user.username)
        except Exception as exc:
            print(f"Asana task creation failed: {exc}")

    # --- Return combined results ---
    return JsonResponse({
        "sent": sent,
        "skipped": skipped,
        "curation_issues": curation_issues,
        "message": (
            "Some submissions could not be sent for validation."
            if curation_issues or any(skipped.values())
            else "All submissions successfully sent for validation."
        ),
        "redirect": reverse("ingest:index"),
    })


def check_collection_directories(coll, current_user):
    """
    Verifies that the filesystem directory structure matches expected dataset directories
    using the collection's stored data_path. Returns a structured dict for UI display.
    """

    # Use the path recorded in the collection itself
    base_dir = Path(coll.data_path).expanduser()

    # --- 1. Directory missing entirely ---
    if not base_dir.exists():
        return {
            "status": "missing_path",
            "title": "Collection Directory Missing",
            "message": (
                f"The collection path recorded in metadata ({coll.data_path}) "
                "does not exist on disk."
            ),
            "suggestion": (
                "Contact bil-support@psc.edu so we can investigate why the directory creation failed "
            ),
            "missing": [],
            "extra": [],
        }

    # --- 2. Permission error accessing directory ---
    try:
        actual_dirs = sorted([p.name for p in base_dir.iterdir() if p.is_dir()])
    except PermissionError:
        return {
            "status": "permission_error",
            "title": "Permission Error",
            "message": (
                f"Permission denied when reading {base_dir}. "
                "The web service or test user may not have filesystem access."
            ),
            "suggestion": (
                "Verify directory ownership and permissions. "
                "The process running Django must have read access to all subdirectories."
            ),
            "missing": [],
            "extra": [],
        }

    # --- 3. Compare expected vs actual dataset subdirectories ---
    datasets = Dataset.objects.filter(sheet__collection=coll)
    expected_dirs = sorted([
        Path(ds.bildirectory).name.strip("/")
        for ds in datasets if ds.bildirectory
    ])

    missing = [d for d in expected_dirs if d not in actual_dirs]
    extra = [d for d in actual_dirs if d not in expected_dirs]

    # --- 4. No issues ---
    if not missing and not extra:
        return {
            "status": "ok",
            "title": "Directories Verified",
            "message": "All expected dataset directories are present and match metadata.",
            "missing": [],
            "extra": [],
        }

    # --- 5. Directory mismatch ---
    details = []
    if missing:
        details.append(f"Missing expected directories: {', '.join(missing)}")
    if extra:
        details.append(f"Unexpected extra directories found: {', '.join(extra)}")

    return {
        "status": "mismatch",
        "title": "Directory Mismatch Detected",
        "message": (
            "The directories present under this collection’s data_path do not match "
            "the dataset directories listed in metadata."
        ),
        "details": " | ".join(details),
        "suggestion": (
            "Add any missing directories listed in metadata, or remove any extras "
            "not referenced there, before re-submitting for validation."
        ),
        "missing": missing,
        "extra": extra,
    }

@login_required
def refresh_tables(request):
    """Return updated eligible and validation-in-progress table HTML (mirrors SubmitRequestCollectionList logic)."""
    user = request.user

    # Base set: user’s collections excluding already fully completed ones
    base_qs = (Collection.objects
               .filter(user=user)
               .exclude(Q(submission_status=Collection.SUCCESS) &
                        Q(validation_status=Collection.SUCCESS)))

    # Subqueries
    has_sheet_sq = Sheet.objects.filter(collection=OuterRef('pk'))
    has_requested_sq = EventsLog.objects.filter(
        collection_id=OuterRef('pk'),
        event_type='request_validation',
    )

    # Annotate and categorize
    annotated = (base_qs
                 .annotate(has_sheet=Exists(has_sheet_sq),
                           has_requested=Exists(has_requested_sq)))

    eligible = annotated.filter(has_sheet=True, has_requested=False)
    needs_metadata = annotated.filter(has_sheet=False)
    already_requested = annotated.filter(has_requested=True)

    return render(request, "ingest/_tables_refresh.html", {
        "eligible_collections": eligible.distinct(),
        "needs_metadata_collections": needs_metadata.distinct(),
        "already_requested_collections": already_requested.distinct(),
        "pi": People.objects.filter(auth_user_id_id=user.id).exists(),
    })

def _create_asana_tasks(bil_uuids, username):
    """Create Asana tasks for the submitted collections (UUID only)."""

    token = settings.ASANA_PAT
    project_id = settings.ASANA_PROJECT_ID
    gid = settings.ASANA_GID  # Section ID for "Submitted/Resubmitted"

    if not token or not project_id or not gid:
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    task_url = "https://app.asana.com/api/1.0/tasks"
    section_url = f"https://app.asana.com/api/1.0/sections/{gid}/addTask"

    for bil_uuid in bil_uuids:
        try:
            payload = {
                "data": {
                    "name": bil_uuid,  # Just the UUID
                    "notes": f"User {username} submitted collection {bil_uuid}",
                    "projects": [project_id],
                }
            }

            # Create the task
            response = requests.post(task_url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            task_gid = response.json()["data"]["gid"]

            # Move the task into the section
            section_payload = {
                "data": {
                    "task": task_gid
                }
            }
            section_response = requests.post(section_url, headers=headers, json=section_payload, timeout=10)
            section_response.raise_for_status()

            print(f"✅ Created Asana task for UUID: {bil_uuid}")

        except Exception as exc:
            print(f"❌ Asana task creation failed for {bil_uuid}: {exc}")


@login_required
def collection_create(request):
    current_user = request.user
    try:
        people = People.objects.get(auth_user_id_id = current_user.id)
        project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    except ObjectDoesNotExist:
        messages.info(request, 'Error: Your account is likely not fully set up. Follow along with your Sign Up ticket on bil-support and provide the appropriate Grant Name and Number to the Project you will be submitting for. If you have already done so, kindly nudge us to complete your account creation.')
        return redirect('/')
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False
    """ Create a collection. """
    # We cache the staging area location, so that we can show it in the GET and
    # later use it during creation (POST)
    if cache.get('host_and_path'):
        host_and_path = cache.get('host_and_path')
        data_path = cache.get('data_path')
        bil_uuid = cache.get('bil_uuid')
        bil_user = cache.get('bil_user')
    else:
        #FOR PRODUCTION
        top_level_dir = settings.STAGING_AREA_ROOT
        #FOR LOCAL DEVELOPMENT
        #top_level_dir = '/Users/luketuite/newbil/aug_bil_site/lz'
        #shortens uuid
        uuidhex = (uuid.uuid4()).hex
        str1 = uuidhex[0:16]
        str2 = uuidhex[16:]
        str3 = "%x" % (int(str1,16)^int(str2,16))
        bil_uuid = str3.zfill(16)
        #this should make uuid unique or just redirect to home page if collision.
        uu = UUID(useduuid=bil_uuid)
        try:
           uu.save()
        except:
           return redirect('ingest:index') 
        #data_path = "{}/bil_data/{}/{:02d}/{}".format(
        #    top_level_dir,
        #    datetime.datetime.now().year,
        #    datetime.datetime.now().month,
        #    str(uuid.uuid4()))
        data_path = "{}/{}/{}".format(
            top_level_dir,
            request.user,
            bil_uuid)
        host_and_path = "{}@{}:{}".format(
            request.user, settings.IMG_DATA_HOST, data_path)
        bil_user = "{}".format(request.user)
        cache.set('host_and_path', host_and_path, 30)
        cache.set('data_path', data_path, 30)
        cache.set('bil_uuid', bil_uuid, 30)
        cache.set('bil_user', bil_user, 30)

    if request.method == "POST":
        # We need to pass in request here, so we can use it to get the user
        form = CollectionForm(request.POST, request=request)
        if form.is_valid():
            # remotely create the directory on some host using fabric and
            # celery
            # note: you should authenticate with ssh keys, not passwords
            if not settings.FAKE_STORAGE_AREA:
                tasks.create_data_path.delay(data_path,bil_user)
            post = form.save(commit=False)
            #post.data_path = host_and_path
            post.data_path = data_path
            post.bil_uuid = bil_uuid
            post.bil_user = bil_user
            post.save()

            time = datetime.now()
            coll_id = Collection.objects.get(id = post.id)
            #coll_id = Collection.objects.filter(bil_uuid = bil_uuid).values_list('id', flat=True)
            proj_id = coll_id.project_id
            
            event = EventsLog(collection_id = coll_id, people_id_id = people.id, project_id_id = proj_id, notes = '', timestamp = time, event_type = 'collection_created')
            event.save()
            cache.delete('host_and_path')
            cache.delete('data_path')
            cache.delete('bil_uuid')
            cache.delete('bil_user')
            messages.success(request, 'Collection successfully created!! Please proceed with metadata upload')
            return redirect('ingest:descriptive_metadata_upload', coll_id.id)
    else:
        form = CollectionForm(request=request)

    project_list = []
    person = People.objects.get(auth_user_id=request.user.id)
    projects = ProjectPeople.objects.filter(people_id=people.id).all()
    for proj in projects:
        project = Project.objects.get(id=proj.project_id_id)  
        project_list.append(project)
  
    collections = Collection.objects.all()
    funder_list = [
        "1-U01-H114812-01",
        "1-U01-MH114819-01",
        "1-U01-MH114824-01",
        "1-U01-MH114825-01",
        "1-U01-MH114829-01",
        "1-U19-MH114821-01",
        "1-U19-MH114830-01",
        "1-U19-MH114831-01",
        "1-U24-MH114827-01",
        "1R24MH114788-01",
        "1R24MH114793-01",
    ]

    return render(
        request,
        'ingest/collection_create.html',
        {'form': form,
         'projects': projects,
         'project_list': project_list, 
         'collections': collections,
         'funder_list': funder_list,
         'host_and_path': host_and_path,
         'pi': pi})

@login_required
def submission_view(request):
    if request.method == 'POST':
        form = CollectionChoice(request.user, request.POST)
        if form.is_valid():
            selected_collection = form.cleaned_data['collection']
            return redirect('ingest:descriptive_metadata_upload', associated_collection=selected_collection.id)
    collections = Collection.objects.filter(user=request.user).exclude(
        submission_status='SUCCESS', validation_status='SUCCESS'
    ).order_by('name')
    return render(request, 'ingest/choose_submission.html', {'collections': collections})

class SubmitValidateCollectionList(LoginRequiredMixin, SingleTableMixin, FilterView):
    """ A list of all a user's collections. """

    table_class = CollectionTable
    model = Collection
    template_name = 'ingest/submit_validate_collection_list.html'
    filterset_class = CollectionFilter

    def get_queryset(self, **kwargs):
        return Collection.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        context['collections'] = Collection.objects.filter(user=self.request.user)
        return context

    def get_filterset_kwargs(self, filterset_class):
        """ Sets the default collection filter status. """
        kwargs = super().get_filterset_kwargs(filterset_class)
        if kwargs["data"] is None:
            kwargs["data"] = {"submit_status": "NOT_SUBMITTED"}
        return kwargs

class SubmitRequestCollectionList(LoginRequiredMixin, SingleTableMixin, FilterView):
    table_class = CollectionRequestTable
    model = Collection
    template_name = 'ingest/submit_request_collection_list.html'
    filterset_class = CollectionFilter
    success_url = reverse_lazy('ingest:collection_list')

    def get_queryset(self, **kwargs):
        return Collection.objects.filter(user=self.request.user)

    def _is_pi(self, request):
        try:
            person = People.objects.get(auth_user_id_id=request.user.id)
            return ProjectPeople.objects.filter(people_id=person.id, is_pi=True).exists()
        except People.DoesNotExist:
            return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user_qs = Collection.objects.filter(user=self.request.user)

        # ✅ Completed bucket (SUCCESS/SUCCESS)
        completed = user_qs.filter(
            submission_status=Collection.SUCCESS,
            validation_status=Collection.SUCCESS,
        )

        # Base set: user’s collections excluding already fully completed ones
        base_qs = user_qs.exclude(
            Q(submission_status=Collection.SUCCESS) &
            Q(validation_status=Collection.SUCCESS)
        )

        has_sheet_sq = Sheet.objects.filter(collection=OuterRef('pk'))
        has_requested_sq = EventsLog.objects.filter(
            collection_id=OuterRef('pk'),
            event_type='request_validation',
        )

        annotated = base_qs.annotate(
            has_sheet=Exists(has_sheet_sq),
            has_requested=Exists(has_requested_sq),
        )

        eligible = annotated.filter(has_sheet=True, has_requested=False)
        needs_metadata = annotated.filter(has_sheet=False)
        already_requested = annotated.filter(has_requested=True)

        context.update({
            'pi': self._is_pi(self.request),
            'eligible_collections': eligible.distinct(),
            'needs_metadata_collections': needs_metadata.distinct(),
            'already_requested_collections': already_requested.distinct(),
            'completed_collections': completed.distinct(),  # ✅ NEW
        })
        return context

    def get_filterset_kwargs(self, filterset_class):
        kwargs = super().get_filterset_kwargs(filterset_class)
        if kwargs["data"] is None:
            kwargs["data"] = {"submit_status": "NOT_SUBMITTED"}
        return kwargs
class CollectionList(LoginRequiredMixin, SingleTableMixin, FilterView):
    """ A list of all a user's collections. """

    table_class = CollectionTable
    model = Collection
    template_name = 'ingest/collection_list.html'
    filterset_class = CollectionFilter

    def get_queryset(self, **kwargs):
        return Collection.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_count'] = Collection.objects.filter(user=self.request.user).count()
        context['filtered_count'] = self.object_list.count()
        return context
         
@login_required
def collection_data_path(request, pk):
    """ Info about the staging area for a user's collection. """

    collection = Collection.objects.get(id=pk)
    host_and_path = collection.data_path
    data_path = host_and_path.split(":")[1]

    return render(
        request,
        'ingest/collection_data_path.html',
        {'collection': collection,
         'host_and_path': host_and_path,
         'data_path': data_path})

@login_required
def collection_detail(request, pk):
    current_user = request.user
    people = People.objects.get(auth_user_id_id=current_user.id)
    project_person = ProjectPeople.objects.filter(people_id=people.id).all()
    pi = any(attribute.is_pi for attribute in project_person)

    try:
        datasets_list = []
        collection = Collection.objects.get(id=pk)
        project = collection.project
        project_consortia = ProjectConsortium.objects.filter(project=project).select_related('consortium')

        consortium_tags = set()
        used_tags = set()

        for project_consortium in project_consortia:
            consortium = project_consortium.consortium
            consortium_tags.update(ConsortiumTag.objects.filter(consortium=consortium).values_list('tag', flat=True))

        # Include tags from BIL consortium
        bil_tags = ConsortiumTag.objects.filter(consortium__short_name='BIL').values_list('tag', flat=True)
        consortium_tags.update(bil_tags)

        # Pull user-specific tags
        user_consortium_short = f"user_{current_user.username}"
        user_tags = ConsortiumTag.objects.filter(consortium__short_name=user_consortium_short).values_list('tag', flat=True)

        sheets = Sheet.objects.filter(collection_id=collection.id).last()
        if sheets:
            datasets = Dataset.objects.filter(sheet_id=sheets.id)
            for d in datasets:
                d.tag_list = list(d.tags.values_list('tag__tag', flat=True))
                used_tags.update(d.tag_list)
                datasets_list.append(d)

        consortium_tags = sorted(consortium_tags)
        user_tags = sorted(user_tags)
        used_tags = sorted(used_tags)
    except ObjectDoesNotExist:
        raise Http404

    descriptive_metadata_queryset = collection.descriptivemetadata_set.last()

    table = DescriptiveMetadataTable(
        DescriptiveMetadata.objects.filter(user=request.user, collection=collection))
    
    return render(
        request,
        'ingest/collection_detail.html',
        {
            'table': table,
            'collection': collection,
            'descriptive_metadata_queryset': descriptive_metadata_queryset,
            'pi': pi,
            'datasets_list': datasets_list,
            'consortium_tags': consortium_tags,
            'user_tags': user_tags,
            'used_tags': used_tags
        }
    )

@login_required
def add_tags(request):
    if request.method == 'POST':
        dataset_id = request.POST.get('dataset_id')
        selected_tags = request.POST.getlist('tag_text[]')
        
        if selected_tags and dataset_id:
            try:
                dataset = Dataset.objects.get(id=dataset_id)
                bil_id = BIL_ID.objects.filter(v2_ds_id=dataset).first()  # Lookup BIL_ID based on dataset
                
                for tag_text in selected_tags:
                    # Lookup the corresponding ConsortiumTag object
                    consortium_tag = ConsortiumTag.objects.filter(tag=tag_text).first()
                    if consortium_tag and not DatasetTag.objects.filter(tag=consortium_tag, dataset=dataset).exists():
                        DatasetTag.objects.create(tag=consortium_tag, dataset=dataset, bil_id=bil_id)
                
                # Fetch the updated list of tags to return in the response
                updated_tags = DatasetTag.objects.filter(dataset=dataset)
                tags_list = [{'id': tag.id, 'text': tag.tag.tag, 'url': reverse('ingest:delete_tag')} for tag in updated_tags]  # Include delete URL
                return JsonResponse({'status': 'success', 'tags': tags_list})
            
            except Dataset.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Dataset not found.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request.'})


@login_required
def add_tags_all(request):
    if request.method == 'POST':
        collection_id = request.POST.get('collection_id')
        selected_tags = request.POST.getlist('tag_text[]')

        if selected_tags and collection_id:
            try:
                collection = Collection.objects.get(id=collection_id)
                sheets = Sheet.objects.filter(collection_id=collection.id).last()
                
                if sheets:
                    datasets = Dataset.objects.filter(sheet_id=sheets.id)
                    
                    for dataset in datasets:
                        bil_id = BIL_ID.objects.filter(v2_ds_id=dataset).first()  # Lookup BIL_ID based on dataset
                        
                        for tag_text in selected_tags:
                            # Lookup the corresponding ConsortiumTag object
                            consortium_tag = ConsortiumTag.objects.filter(tag=tag_text).first()
                            if consortium_tag and not DatasetTag.objects.filter(tag=consortium_tag, dataset=dataset).exists():
                                DatasetTag.objects.create(tag=consortium_tag, dataset=dataset, bil_id=bil_id)

                    # Fetch the updated list of tags to return in the response
                    updated_tags = {}
                    for dataset in datasets:
                        updated_tags[dataset.id] = [{'id': tag.id, 'text': tag.tag.tag, 'url': reverse('ingest:delete_tag')} for tag in dataset.tags.all()]  # Use `tag.tag.tag` for the correct tag name
                    return JsonResponse({'status': 'success', 'updated_tags': updated_tags})
            
            except Collection.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Collection not found.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request.'})

@login_required
def delete_tag(request):
    if request.method == 'POST':
        tag_id = request.POST.get('tag_id')
        
        if tag_id:
            try:
                # Fetch the DatasetTag based on the tag ID
                tag = DatasetTag.objects.get(id=tag_id)
                tag_text = tag.tag.tag  # Get the tag text before deleting
                
                tag.delete()  # Delete the DatasetTag entry
                
                return JsonResponse({'status': 'success', 'tag_text': tag_text})
            except DatasetTag.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Tag not found.'}, status=404)
    return JsonResponse({'status': 'error', 'message': 'Invalid request.'})

@login_required
def delete_tag_all(request):
    if request.method == 'POST':
        collection_id = request.POST.get('collection_id')
        tag_text = request.POST.get('tag_text')

        if collection_id and tag_text:
            try:
                collection = Collection.objects.get(id=collection_id)
                sheets = Sheet.objects.filter(collection_id=collection.id).last()
                if sheets:
                    datasets = Dataset.objects.filter(sheet_id=sheets.id)
                    for dataset in datasets:
                        DatasetTag.objects.filter(tag=tag_text, dataset=dataset).delete()

                    # Fetch the updated list of tags to return in the response
                    updated_tags = {}
                    for dataset in datasets:
                        updated_tags[dataset.id] = [{'id': tag.id, 'tag': tag.tag} for tag in dataset.tags.all()]
                    return JsonResponse({'status': 'success', 'updated_tags': updated_tags})
            except Collection.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Collection not found.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request.'})

@login_required
def create_dataset_linkage(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)

    # All existing linkages for datasets in this collection
    existing_linkages = (
        DatasetLinkage.objects
        .filter(data_id_1_bil__v2_ds_id__sheet__collection_id=collection.id)
        .select_related("data_id_1_bil__v2_ds_id")
        .order_by("data_id_1_bil__v2_ds_id__title")
    )

    # Datasets that already have at least one linkage
    linked_dataset_ids = set(
        existing_linkages.values_list("data_id_1_bil__v2_ds_id_id", flat=True).distinct()
    )

    # Annotate BIL_ID for all datasets in the collection
    bil_id_subq = BIL_ID.objects.filter(v2_ds_id=OuterRef("pk")).values("id")[:1]
    all_datasets = (
        Dataset.objects
        .filter(sheet__collection_id=collection.id)
        .annotate(bil_id=Subquery(bil_id_subq))
        .order_by("title")
    )

    # Show the form only for datasets that do NOT yet have a linkage
    datasets_to_link = all_datasets.exclude(id__in=linked_dataset_ids)

    # Preload BIL IDs for the Select2 search helper (optional)
    bil_ids = list(BIL_ID.objects.values("bil_id", "v2_ds_id__title"))
    bil_id_data = [
        {"bil_id": b["bil_id"], "dataset_title": b.get("v2_ds_id__title") or ""}
        for b in bil_ids
    ]

    if request.method == "POST":
        try:
            created = 0
            with transaction.atomic():
                # Only process rows we actually rendered
                for ds in datasets_to_link:
                    code_id = (request.POST.get(f"code_id_{ds.id}") or "").strip()
                    data_id_2 = (request.POST.get(f"data_id_2_{ds.id}") or "").strip()
                    relationship = (request.POST.get(f"relationship_{ds.id}") or "").strip()
                    description = (request.POST.get(f"description_{ds.id}") or "").strip()

                    if not (code_id and data_id_2 and relationship):
                        continue

                    bil_id_instance = BIL_ID.objects.filter(v2_ds_id=ds).first()
                    if not bil_id_instance:
                        continue

                    # Skip duplicate rows
                    if DatasetLinkage.objects.filter(
                        data_id_1_bil=bil_id_instance,
                        code_id=code_id,
                        data_id_2=data_id_2,
                        relationship=relationship,
                    ).exists():
                        continue

                    DatasetLinkage.objects.create(
                        data_id_1_bil=bil_id_instance,
                        code_id=code_id,
                        data_id_2=data_id_2,
                        relationship=relationship,
                        description=description,
                    )
                    created += 1

            messages.success(request, f"Created {created} linkage{'s' if created != 1 else ''}.")
            return redirect("ingest:create_dataset_linkage", collection_id=collection.id)

        except Exception as e:
            messages.error(request, f"Error saving dataset linkages: {e}")

    return render(
        request,
        "ingest/create_dataset_linkage.html",
        {
            "collection": collection,
            "existing_linkages": existing_linkages,
            "datasets_to_link": datasets_to_link,
            "bil_id_data": bil_id_data,
        },
    )

def get_bil_ids(request):
    query = request.GET.get("q", "").strip()
    
    # Get all BIL_IDs, optionally filtering by the search term
    bil_ids = BIL_ID.objects.all()
    if query:
        bil_ids = bil_ids.filter(bil_id__icontains=query) | bil_ids.filter(v2_ds_id__title__icontains=query)
    
    data = [
        {
            "bil_id": bil.bil_id,
            "dataset_title": bil.v2_ds_id.title if bil.v2_ds_id else ""  # Avoid NoneType errors
        }
        for bil in bil_ids
    ]
    return JsonResponse(data, safe=False)

@login_required
def ondemandSubmission(request, pk):
    coll = Collection.objects.get(id = pk)
    if coll.submission_status == 'SUCCESS' and coll.validation_status == 'SUCCESS':
        first2 = coll.bil_uuid[:2]
        second2 = coll.bil_uuid[2:4]
        path = '/bil/data/' + first2 + '/' + second2 + '/' + coll.bil_uuid + '/'
    else:
        path = coll.data_path
    od = 'https://ondemand.bil.psc.edu/pun/sys/dashboard/files/fs' + path
    return redirect(od)



class CollectionUpdate(LoginRequiredMixin, UpdateView):
    """ Edit an existing collection ."""
    model = Collection
    fields = [
        'name', 'description', 'organization_name', 'lab_name',
        'project_funder', 'project_funder_id'
    ]
    
    def IsPi(request):
        current_user = request.user
        people = People.objects.get(auth_user_id_id = current_user.id)
        project_person = ProjectPeople.objects.filter(people_id = people.id).all()
        for attribute in project_person:
            if attribute.is_pi:
                pi = True
            else:
                pi = False
        return render(request, {'pi':pi})
    template_name = 'ingest/collection_update.html'
    success_url = reverse_lazy('ingest:collection_list')

@login_required
def collection_delete(request, pk):
    current_user = request.user
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False
    """ Delete a collection. """

    collection = Collection.objects.get(pk=pk)
    if request.method == 'POST':
        if collection.submission_status != "SUCCESS":
            data_path = collection.data_path.__str__()
            if not settings.FAKE_STORAGE_AREA:
            # This is what deletes the actual directory associated with the
            # staging area

                tasks.delete_data_path.delay(data_path)
            collection.delete()
            messages.success(request, 'Collection successfully deleted')
            return redirect('ingest:collection_list')
        else:
            messages.error(request, 'This collection is public, it cannot be deleted. If this is incorrect contact us at bil-support@psc.edu')
    return render(
        request, 'ingest/collection_delete.html', {'collection': collection, 'pi':pi})

def check_contributors_sheet(filename):
    errors = []
    workbook = xlrd.open_workbook(filename)
    sheetname = 'Contributors'
    contributors_sheet = workbook.sheet_by_name(sheetname)
    colheads = ['contributorName', 'Creator', 'contributorType',
                'nameType', 'nameIdentifier', 'nameIdentifierScheme',
                'affiliation', 'affiliationIdentifier', 'affiliationIdentifierScheme']
    creator = ['Yes', 'No']
    contributortype = ['ProjectLeader', 'ResearchGroup', 'ContactPerson', 'DataCollector',
                       'DataCurator', 'ProjectManager', 'ProjectMember', 'RelatedPerson',
                       'Researcher', 'Other']
    nametype = ['Personal', 'Organizational']
    nameidentifierscheme = ['ORCID', 'ISNI', 'ROR', 'GRID', 'RRID']
    affiliationidentifierscheme = ['ORCID', 'ISNI', 'ROR', 'GRID', 'RRID']
    header_row = 2
    cols = contributors_sheet.row_values(header_row)
    for i in range(len(colheads)):
        if i >= len(cols) or cols[i] != colheads[i]:
            found = cols[i] if i < len(cols) else ''
            errors.append({"row": header_row, "col": i,
                           "message": f'Expected heading "{colheads[i]}", found "{found}"'})
    if errors:
        return errors
    for i in range(6, contributors_sheet.nrows):
        cols = contributors_sheet.row_values(i)
        if cols[0] == "":
            errors.append({"row": i, "col": 0, "message": f'"{colheads[0]}" is required'})
        if cols[1] == "":
            errors.append({"row": i, "col": 1, "message": f'"{colheads[1]}" is required'})
        elif cols[1] not in creator:
            errors.append({"row": i, "col": 1, "message": f'"{colheads[1]}" invalid value "{cols[1]}" — must be one of: {", ".join(creator)}'})
        if cols[2] == "":
            errors.append({"row": i, "col": 2, "message": f'"{colheads[2]}" is required'})
        elif cols[2] not in contributortype:
            errors.append({"row": i, "col": 2, "message": f'"{colheads[2]}" invalid value "{cols[2]}" — must be one of: {", ".join(contributortype)}'})
        if cols[3] == "":
            errors.append({"row": i, "col": 3, "message": f'"{colheads[3]}" is required'})
        elif cols[3] not in nametype:
            errors.append({"row": i, "col": 3, "message": f'"{colheads[3]}" invalid value "{cols[3]}" — must be one of: {", ".join(nametype)}'})
        if cols[3] == "Personal":
            if cols[4] == "":
                errors.append({"row": i, "col": 4, "message": f'"{colheads[4]}" is required when nameType is Personal'})
            if cols[5] == "":
                errors.append({"row": i, "col": 5, "message": f'"{colheads[5]}" is required when nameType is Personal'})
            elif cols[5] not in nameidentifierscheme:
                errors.append({"row": i, "col": 5, "message": f'"{colheads[5]}" invalid value "{cols[5]}" — must be one of: {", ".join(nameidentifierscheme)}'})
        if cols[6] == "":
            errors.append({"row": i, "col": 6, "message": f'"{colheads[6]}" is required'})
        if cols[7] == "":
            errors.append({"row": i, "col": 7, "message": f'"{colheads[7]}" is required'})
        if cols[8] == "":
            errors.append({"row": i, "col": 8, "message": f'"{colheads[8]}" is required'})
        elif cols[8] not in affiliationidentifierscheme:
            errors.append({"row": i, "col": 8, "message": f'"{colheads[8]}" invalid value "{cols[8]}" — must be one of: {", ".join(affiliationidentifierscheme)}'})
    return errors

def check_funders_sheet(filename):
    errors = []
    workbook = xlrd.open_workbook(filename)
    sheetname = 'Funders'
    funders_sheet = workbook.sheet_by_name(sheetname)
    colheads = ['funderName', 'fundingReferenceIdentifier', 'fundingReferenceIdentifierType',
                'awardNumber', 'awardTitle']
    fundingReferenceIdentifierType = ['ROR', 'GRID', 'ORCID', 'ISNI']
    header_row = 3
    cols = funders_sheet.row_values(header_row)
    for i in range(len(colheads)):
        if i >= len(cols) or cols[i] != colheads[i]:
            found = cols[i] if i < len(cols) else ''
            errors.append({"row": header_row, "col": i,
                           "message": f'Expected heading "{colheads[i]}", found "{found}"'})
    if errors:
        return errors
    for i in range(6, funders_sheet.nrows):
        cols = funders_sheet.row_values(i)
        if cols[0] == "":
            errors.append({"row": i, "col": 0, "message": f'"{colheads[0]}" is required'})
        if cols[1] == "":
            errors.append({"row": i, "col": 1, "message": f'"{colheads[1]}" is required'})
        if cols[2] == "":
            errors.append({"row": i, "col": 2, "message": f'"{colheads[2]}" is required'})
        elif cols[2] not in fundingReferenceIdentifierType:
            errors.append({"row": i, "col": 2, "message": f'"{colheads[2]}" invalid value "{cols[2]}" — must be one of: {", ".join(fundingReferenceIdentifierType)}'})
        if cols[3] == "":
            errors.append({"row": i, "col": 3, "message": f'"{colheads[3]}" is required'})
        if cols[4] == "":
            errors.append({"row": i, "col": 4, "message": f'"{colheads[4]}" is required'})
    return errors

def check_publication_sheet(filename):
    errors = []
    workbook = xlrd.open_workbook(filename)
    sheetname = 'Publication'
    publication_sheet = workbook.sheet_by_name(sheetname)
    colheads = ['relatedIdentifier', 'relatedIdentifierType', 'PMCID', 'relationType', 'citation']
    relatedIdentifierType = ['arcXiv', 'DOI', 'PMID', 'ISBN']
    relationType = ['IsCitedBy', 'IsDocumentedBy']
    header_row = 3
    cols = publication_sheet.row_values(header_row)
    for i in range(len(colheads)):
        if i >= len(cols) or cols[i] != colheads[i]:
            found = cols[i] if i < len(cols) else ''
            errors.append({"row": header_row, "col": i,
                           "message": f'Expected heading "{colheads[i]}", found "{found}"'})
    if errors:
        return errors
    for i in range(6, publication_sheet.nrows):
        cols = publication_sheet.row_values(i)
        if cols[1] != '':
            if cols[1] not in relatedIdentifierType:
                errors.append({"row": i, "col": 1, "message": f'"{colheads[1]}" invalid value "{cols[1]}" — must be one of: {", ".join(relatedIdentifierType)}'})
        if cols[3] != '':
            if cols[3] not in relationType:
                errors.append({"row": i, "col": 3, "message": f'"{colheads[3]}" invalid value "{cols[3]}" — must be one of: {", ".join(relationType)}'})
    return errors

def check_instrument_sheet(filename):
    errors = []
    workbook = xlrd.open_workbook(filename)
    sheetname = 'Instrument'
    instrument_sheet = workbook.sheet_by_name(sheetname)
    colheads = ['MicroscopeType', 'MicroscopeManufacturerAndModel', 'ObjectiveName',
                'ObjectiveImmersion', 'ObjectiveNA', 'ObjectiveMagnification', 'DetectorType',
                'DetectorModel', 'IlluminationTypes', 'IlluminationWavelength',
                'DetectionWavelength', 'SampleTemperature']
    header_row = 3
    cols = instrument_sheet.row_values(header_row)
    for i in range(len(colheads)):
        if i >= len(cols) or cols[i] != colheads[i]:
            found = cols[i] if i < len(cols) else ''
            errors.append({"row": header_row, "col": i,
                           "message": f'Expected heading "{colheads[i]}", found "{found}"'})
    if errors:
        return errors
    for i in range(6, instrument_sheet.nrows):
        cols = instrument_sheet.row_values(i)
        if cols[0] == "":
            errors.append({"row": i, "col": 0, "message": f'"{colheads[0]}" is required'})
    return errors


def check_dataset_sheet(filename):
    errors = []
    workbook = xlrd.open_workbook(filename)
    sheetname = 'Dataset'
    dataset_sheet = workbook.sheet_by_name(sheetname)
    colheads = ['BILDirectory', 'title', 'socialMedia', 'subject',
                'Subjectscheme', 'rights', 'rightsURI', 'rightsIdentifier', 'Image',
                'GeneralModality', 'Technique', 'Other', 'Abstract', 'Methods', 'TechnicalInfo']
    GeneralModality = ['cell morphology', 'connectivity', 'population imaging',
                       'spatial transcriptomics', 'other', 'anatomy', 'histology imaging', 'multimodal']
    Technique = ['anterograde tracing', 'retrograde transynaptic tracing', 'TRIO tracing',
                 'smFISH', 'DARTFISH', 'MERFISH', 'Patch-seq', 'fMOST', 'other',
                 'cre-dependent anterograde tracing', 'enhancer virus labeling', 'FISH',
                 'MORF genetic sparse labeling', 'mouselight', 'neuron morphology reconstruction',
                 'retrograde tracing', 'retrograde transsynaptic tracing', 'seqFISH', 'STPT',
                 'VISor', 'confocal microscopy']
    header_row = 3
    cols = dataset_sheet.row_values(header_row)
    for i in range(len(colheads)):
        if i >= len(cols) or cols[i] != colheads[i]:
            found = cols[i] if i < len(cols) else ''
            errors.append({"row": header_row, "col": i,
                           "message": f'Expected heading "{colheads[i]}", found "{found}"'})
    if errors:
        return errors
    for i in range(6, dataset_sheet.nrows):
        cols = dataset_sheet.row_values(i)
        if cols[0] == "":
            errors.append({"row": i, "col": 0, "message": f'"{colheads[0]}" is required'})
        if cols[1] == "":
            errors.append({"row": i, "col": 1, "message": f'"{colheads[1]}" is required'})
        if cols[5] == "":
            errors.append({"row": i, "col": 5, "message": f'"{colheads[5]}" is required'})
        if cols[6] == "":
            errors.append({"row": i, "col": 6, "message": f'"{colheads[6]}" is required'})
        if cols[7] == "":
            errors.append({"row": i, "col": 7, "message": f'"{colheads[7]}" is required'})
        if cols[9] != '':
            if cols[9] not in GeneralModality:
                errors.append({"row": i, "col": 9, "message": f'"{colheads[9]}" invalid value "{cols[9]}" — must be one of: {", ".join(GeneralModality)}'})
        if cols[10] == "":
            errors.append({"row": i, "col": 10, "message": f'"{colheads[10]}" is required'})
        elif cols[10] not in Technique:
            errors.append({"row": i, "col": 10, "message": f'"{colheads[10]}" invalid value "{cols[10]}" — must be one of: {", ".join(Technique)}'})
        if (cols[9] == "other" or cols[10] == "other") and cols[11] == "":
            errors.append({"row": i, "col": 11, "message": f'"{colheads[11]}" is required when GeneralModality or Technique is "other"'})
        if cols[12] == "":
            errors.append({"row": i, "col": 12, "message": f'"{colheads[12]}" is required'})
    return errors

def check_specimen_sheet(filename):
    errors = []
    workbook = xlrd.open_workbook(filename)
    sheetname = 'Specimen'
    specimen_sheet = workbook.sheet_by_name(sheetname)
    colheads = ['LocalID', 'Species', 'NCBITaxonomy', 'Age', 'Ageunit', 'Sex', 'Genotype',
                'OrganLocalID', 'OrganName', 'SampleLocalID', 'Atlas', 'Locations']
    Sex = ['Male', 'Female', 'Unknown']
    header_row = 3
    cols = specimen_sheet.row_values(header_row)
    for i in range(len(colheads)):
        if i >= len(cols) or cols[i] != colheads[i]:
            found = cols[i] if i < len(cols) else ''
            errors.append({"row": header_row, "col": i,
                           "message": f'Expected heading "{colheads[i]}", found "{found}"'})
    if errors:
        return errors
    for i in range(6, specimen_sheet.nrows):
        cols = specimen_sheet.row_values(i)
        if cols[1] == "":
            errors.append({"row": i, "col": 1, "message": f'"{colheads[1]}" is required'})
        if cols[2] == "":
            errors.append({"row": i, "col": 2, "message": f'"{colheads[2]}" is required'})
        if cols[3] == "":
            errors.append({"row": i, "col": 3, "message": f'"{colheads[3]}" is required'})
        if cols[4] == "":
            errors.append({"row": i, "col": 4, "message": f'"{colheads[4]}" is required'})
        if cols[5] == "":
            errors.append({"row": i, "col": 5, "message": f'"{colheads[5]}" is required'})
        elif cols[5] not in Sex:
            errors.append({"row": i, "col": 5, "message": f'"{colheads[5]}" invalid value "{cols[5]}" — must be one of: {", ".join(Sex)}'})
        if cols[9] == "":
            errors.append({"row": i, "col": 9, "message": f'"{colheads[9]}" is required'})
    return errors

def check_image_sheet(filename):
    errors = []
    workbook = xlrd.open_workbook(filename)
    sheetname = 'Image'
    image_sheet = workbook.sheet_by_name(sheetname)
    colheads = ['xAxis', 'obliqueXdim1', 'obliqueXdim2', 'obliqueXdim3',
                'yAxis', 'obliqueYdim1', 'obliqueYdim2', 'obliqueYdim3',
                'zAxis', 'obliqueZdim1', 'obliqueZdim2', 'obliqueZdim3',
                'landmarkName', 'landmarkX', 'landmarkY', 'landmarkZ',
                'Number', 'displayColor', 'Representation', 'Flurophore',
                'stepSizeX', 'stepSizeY', 'stepSizeZ', 'stepSizeT',
                'Channels', 'Slices', 'z', 'Xsize', 'Ysize', 'Zsize',
                'Gbytes', 'Files', 'DimensionOrder']
    zAxis = yAxis = xAxis = ['right-to-left', 'left-to-right', 'anterior-to-posterior',
                              'posterior-to-anterior', 'superior-to-inferior',
                              'inferior-to-superior', 'oblique', 'NA', 'N/A', 'na']
    obliqueXdim1 = obliqueYdim1 = ObliqueZdim1 = ['Right', 'Left']
    obliqueXdim2 = obliqueYdim2 = ObliqueZdim2 = ['Anterior', 'Posterior']
    obliqueXdim3 = obliqueYdim3 = ObliqueZdim3 = ['Superior', 'Inferior']
    header_row = 3
    cols = image_sheet.row_values(header_row)
    for i in range(len(colheads)):
        if i >= len(cols) or cols[i] != colheads[i]:
            found = cols[i] if i < len(cols) else ''
            errors.append({"row": header_row, "col": i,
                           "message": f'Expected heading "{colheads[i]}", found "{found}"'})
    if errors:
        return errors
    for i in range(6, image_sheet.nrows):
        cols = image_sheet.row_values(i)
        if cols[0] == "":
            errors.append({"row": i, "col": 0, "message": f'"{colheads[0]}" is required'})
        elif cols[0] not in xAxis:
            errors.append({"row": i, "col": 0, "message": f'"{colheads[0]}" invalid value "{cols[0]}" — must be one of: {", ".join(xAxis)}'})
        if cols[1] != "" and cols[1] not in obliqueXdim1:
            errors.append({"row": i, "col": 1, "message": f'"{colheads[1]}" invalid value "{cols[1]}" — must be one of: {", ".join(obliqueXdim1)}'})
        if cols[2] != "" and cols[2] not in obliqueXdim2:
            errors.append({"row": i, "col": 2, "message": f'"{colheads[2]}" invalid value "{cols[2]}" — must be one of: {", ".join(obliqueXdim2)}'})
        if cols[3] != "" and cols[3] not in obliqueXdim3:
            errors.append({"row": i, "col": 3, "message": f'"{colheads[3]}" invalid value "{cols[3]}" — must be one of: {", ".join(obliqueXdim3)}'})
        if cols[4] == "":
            errors.append({"row": i, "col": 4, "message": f'"{colheads[4]}" is required'})
        elif cols[4] not in yAxis:
            errors.append({"row": i, "col": 4, "message": f'"{colheads[4]}" invalid value "{cols[4]}" — must be one of: {", ".join(yAxis)}'})
        if cols[5] != "" and cols[5] not in obliqueYdim1:
            errors.append({"row": i, "col": 5, "message": f'"{colheads[5]}" invalid value "{cols[5]}" — must be one of: {", ".join(obliqueYdim1)}'})
        if cols[6] != "" and cols[6] not in obliqueYdim2:
            errors.append({"row": i, "col": 6, "message": f'"{colheads[6]}" invalid value "{cols[6]}" — must be one of: {", ".join(obliqueYdim2)}'})
        if cols[7] != "" and cols[7] not in obliqueYdim3:
            errors.append({"row": i, "col": 7, "message": f'"{colheads[7]}" invalid value "{cols[7]}" — must be one of: {", ".join(obliqueYdim3)}'})
        if cols[8] == "":
            errors.append({"row": i, "col": 8, "message": f'"{colheads[8]}" is required'})
        elif cols[8] not in zAxis:
            errors.append({"row": i, "col": 8, "message": f'"{colheads[8]}" invalid value "{cols[8]}" — must be one of: {", ".join(zAxis)}'})
        if cols[9] != "" and cols[9] not in ObliqueZdim1:
            errors.append({"row": i, "col": 9, "message": f'"{colheads[9]}" invalid value "{cols[9]}" — must be one of: {", ".join(ObliqueZdim1)}'})
        if cols[10] != "" and cols[10] not in ObliqueZdim2:
            errors.append({"row": i, "col": 10, "message": f'"{colheads[10]}" invalid value "{cols[10]}" — must be one of: {", ".join(ObliqueZdim2)}'})
        if cols[11] != "" and cols[11] not in ObliqueZdim3:
            errors.append({"row": i, "col": 11, "message": f'"{colheads[11]}" invalid value "{cols[11]}" — must be one of: {", ".join(ObliqueZdim3)}'})
        if cols[16] == "":
            errors.append({"row": i, "col": 16, "message": f'"{colheads[16]}" is required'})
        if cols[17] == "":
            errors.append({"row": i, "col": 17, "message": f'"{colheads[17]}" is required'})
        if cols[20] == "":
            errors.append({"row": i, "col": 20, "message": f'"{colheads[20]}" is required'})
        if cols[21] == "":
            errors.append({"row": i, "col": 21, "message": f'"{colheads[21]}" is required'})
    return errors


def check_swc_sheet(filename):
    errors = []
    workbook = xlrd.open_workbook(filename)
    sheetname = 'SWC'
    swc_sheet = workbook.sheet_by_name(sheetname)
    colheads = ['tracingFile', 'sourceData', 'sourceDataSample', 'sourceDataSubmission',
                'coordinates', 'coordinatesRegistration', 'brainRegion', 'brainRegionAtlas',
                'brainRegionAtlasName', 'brainRegionAxonalProjection',
                'brainRegionDendriticProjection', 'neuronType', 'segmentTags',
                'proofreadingLevel', 'Notes']
    coordinatesRegistration = ['Yes', 'No']
    header_row = 3
    cols = swc_sheet.row_values(header_row)
    for i in range(len(colheads)):
        if i >= len(cols) or cols[i] != colheads[i]:
            found = cols[i] if i < len(cols) else ''
            errors.append({"row": header_row, "col": i,
                           "message": f'Expected heading "{colheads[i]}", found "{found}"'})
    if errors:
        return errors
    for i in range(6, swc_sheet.nrows):
        cols = swc_sheet.row_values(i)
        if cols[0] == "":
            errors.append({"row": i, "col": 0, "message": f'"{colheads[0]}" is required'})
        if cols[5] == "":
            errors.append({"row": i, "col": 5, "message": f'"{colheads[5]}" is required'})
        elif cols[5] not in coordinatesRegistration:
            errors.append({"row": i, "col": 5, "message": f'"{colheads[5]}" invalid value "{cols[5]}" — must be one of: {", ".join(coordinatesRegistration)}'})
        elif cols[5] == 'Yes':
            if cols[6] == "":
                errors.append({"row": i, "col": 6, "message": f'"{colheads[6]}" is required when coordinatesRegistration is Yes'})
            if cols[7] == "":
                errors.append({"row": i, "col": 7, "message": f'"{colheads[7]}" is required when coordinatesRegistration is Yes'})
            if cols[8] == "":
                errors.append({"row": i, "col": 8, "message": f'"{colheads[8]}" is required when coordinatesRegistration is Yes'})
    return errors

def check_spatial_sheet(filename):
    errors = []
    workbook = xlrd.open_workbook(filename)
    sheetname = 'Spatial'
    try:
        spatial_sheet = workbook.sheet_by_name(sheetname)
    except xlrd.biffh.XLRDError:
        errors.append({"row": 0, "col": 0, "message": 'Tab "Spatial" not found in spreadsheet'})
        return errors

    colheads = [
        'DataAvailability', 'HistologicalStainName', 'NuclearStainName', 'ProbeSetDOI',
        'ProbeSequencesDOI', 'LightTreatmentTime', 'LightTreatmentTimeUnits',
        'NumberTargetedRNA', 'GenePanelName', 'PlatformName', 'MachineName',
        'MachineSoftwareVersion', 'NumberZSections', 'SegmentationMethod',
        'SegmentationModel', 'SegmentationMethodVersion', 'ClusteringMethod',
        'LabelTransferMethod', 'LabelTransferReference', 'NuclearImageTransform',
        'HistologicalImageTransform', 'FilterCriteria', 'XYZPosition', 'CellID',
        'CellCentroidLocation', 'CellAreaVolume'
    ]
    data_availability_cv = ['raw', 'segmented', 'raw and segmented']
    platform_name_cv = ['MERSCOPE', 'DBit-Seq', 'Slide-Tags', 'Stereo-seq', 'Xenium']
    header_row = 3
    cols = spatial_sheet.row_values(header_row)
    for i in range(len(colheads)):
        sheet_val = cols[i] if i < len(cols) else ""
        if sheet_val != colheads[i]:
            errors.append({"row": header_row, "col": i,
                           "message": f'Expected heading "{colheads[i]}", found "{sheet_val}"'})
    if errors:
        return errors

    def get_val(row_vals, idx):
        return "" if idx >= len(row_vals) else str(row_vals[idx]).strip()

    for i in range(6, spatial_sheet.nrows):
        row_vals = spatial_sheet.row_values(i)
        if not any(str(v).strip() for v in row_vals):
            continue
        val = get_val(row_vals, 0)
        if val == "":
            errors.append({"row": i, "col": 0, "message": f'"{colheads[0]}" is required'})
        elif val not in data_availability_cv:
            errors.append({"row": i, "col": 0, "message": f'"{colheads[0]}" invalid value "{val}" — must be one of: {", ".join(data_availability_cv)}'})
        val = get_val(row_vals, 5)
        if val != "":
            try:
                float(val)
            except (ValueError, TypeError):
                errors.append({"row": i, "col": 5, "message": f'"{colheads[5]}" must be numeric'})
        val = get_val(row_vals, 7)
        if val != "":
            try:
                int(float(val))
            except (ValueError, TypeError):
                errors.append({"row": i, "col": 7, "message": f'"{colheads[7]}" must be an integer'})
        val = get_val(row_vals, 9)
        if val != "" and val not in platform_name_cv:
            errors.append({"row": i, "col": 9, "message": f'"{colheads[9]}" invalid value "{val}" — must be one of: {", ".join(platform_name_cv)}'})
        file_cols = [22, 23, 24, 25]
        any_file_val = any(get_val(row_vals, idx) != "" for idx in file_cols)
        if any_file_val:
            for idx in file_cols:
                if get_val(row_vals, idx) == "":
                    errors.append({"row": i, "col": idx, "message": f'"{colheads[idx]}" is required when any file column is filled'})
    return errors

def ingest_contributors_sheet(filename):
    fn = xlrd.open_workbook(filename)
    contributors_sheet = fn.sheet_by_name('Contributors')
    keys = [contributors_sheet.cell(2, col).value for col in range(contributors_sheet.ncols)]
    contributors = []
    for row in range(6,contributors_sheet.nrows):
        values = {keys[col]: contributors_sheet.cell(row, col).value
            for col in range(contributors_sheet.ncols)}
        contributors.append(values)
    return contributors

def ingest_funders_sheet(filename):
    fn = xlrd.open_workbook(filename)
    funders_sheet = fn.sheet_by_name('Funders')
    keys = [funders_sheet.cell(3, col).value for col in range(funders_sheet.ncols)]   
    funders = []
    for row in range(6, funders_sheet.nrows):
        values={keys[col]: funders_sheet.cell(row,col).value
            for col in range(funders_sheet.ncols)}
        funders.append(values)
    return funders

def ingest_publication_sheet(filename):
    fn = xlrd.open_workbook(filename)
    publication_sheet = fn.sheet_by_name('Publication')
    keys = [publication_sheet.cell(3, col).value for col in range(publication_sheet.ncols)]   
    publications = []
    for row in range(6, publication_sheet.nrows):
        values={keys[col]: publication_sheet.cell(row,col).value
            for col in range(publication_sheet.ncols)}
        publications.append(values)

    return publications

def ingest_instrument_sheet(filename):
    fn = xlrd.open_workbook(filename)
    instrument_sheet = fn.sheet_by_name('Instrument')
    keys = [instrument_sheet.cell(3,col).value for col in range(instrument_sheet.ncols)]
    instruments = []
    for row in range(6, instrument_sheet.nrows):
        values={keys[col]: instrument_sheet.cell(row,col).value
            for col in range(instrument_sheet.ncols)}
        instruments.append(values)

    return instruments

def ingest_dataset_sheet(filename):
    fn = xlrd.open_workbook(filename)
    dataset_sheet = fn.sheet_by_name('Dataset')
    keys = [dataset_sheet.cell(3,col).value for col in range(dataset_sheet.ncols)]
    datasets = []
    for row in range(6, dataset_sheet.nrows):
        values={keys[col]: dataset_sheet.cell(row,col).value
            for col in range(dataset_sheet.ncols)}
        datasets.append(values)
    return datasets

def ingest_specimen_sheet(filename):
    fn = xlrd.open_workbook(filename)
    specimen_sheet = fn.sheet_by_name('Specimen')
    keys = [specimen_sheet.cell(3,col).value for col in range(specimen_sheet.ncols)] 
    specimen_set = []
    for row in range(6, specimen_sheet.nrows):
        values={keys[col]: specimen_sheet.cell(row,col).value
            for col in range(specimen_sheet.ncols)}
        specimen_set.append(values)

    return specimen_set

def ingest_image_sheet(filename):
    fn = xlrd.open_workbook(filename)
    image_sheet = fn.sheet_by_name('Image')
    keys = [image_sheet.cell(3,col).value for col in range(image_sheet.ncols)]
    images = []
    for row in range(6, image_sheet.nrows):
        values={keys[col]: image_sheet.cell(row,col).value
            for col in range(image_sheet.ncols)}
        images.append(values)
    return images

def ingest_swc_sheet(filename):
    fn = xlrd.open_workbook(filename)
    swc_sheet = fn.sheet_by_name('SWC')
    keys = [swc_sheet.cell(3,col).value for col in range(swc_sheet.ncols)]
    swcs = []
    for row in range(6, swc_sheet.nrows):
        values={keys[col]: swc_sheet.cell(row,col).value
            for col in range(swc_sheet.ncols)}
        swcs.append(values)
    return swcs

def ingest_spatial_sheet(filename):
    fn = xlrd.open_workbook(filename)
    spatial_sheet = fn.sheet_by_name('Spatial')
    keys = [spatial_sheet.cell(3, col).value for col in range(spatial_sheet.ncols)]
    spatials = []
    for row in range(6, spatial_sheet.nrows):
        values = {
            keys[col]: spatial_sheet.cell(row, col).value
            for col in range(spatial_sheet.ncols)
        }

        # Skip completely empty rows
        if not any(str(v).strip() for v in values.values()):
            continue

        spatials.append(values)
    return spatials

def save_sheet_row(ingest_method, filename, collection):
    try:
        sheet = Sheet(filename=filename, date_uploaded=datetime.now(), collection_id=collection.id, ingest_method = ingest_method)
        sheet.save()
    except Exception as e:
        print(e)
    return sheet

def save_contributors_sheet(contributors, sheet):
    try:
        for c in contributors:
            contributorname = c['contributorName']
            creator = c['Creator']
            contributortype = c['contributorType']
            nametype = c['nameType']
            nameidentifier = c['nameIdentifier']
            nameidentifierscheme = c['nameIdentifierScheme']
            affiliation = c['affiliation']
            affiliationidentifier = c['affiliationIdentifier']
            affiliationidentifierscheme = c['affiliationIdentifierScheme']
            
            contributor = Contributor(contributorname=contributorname, creator=creator, contributortype=contributortype, nametype=nametype, nameidentifier=nameidentifier, nameidentifierscheme=nameidentifierscheme, affiliation=affiliation, affiliationidentifier=affiliationidentifier, affiliationidentifierscheme=affiliationidentifierscheme, sheet_id=sheet.id)
            contributor.save()

        return True
    except Exception as e:
        print(repr(e))
        return False

def save_funders_sheet(funders, sheet):
    try:
        for f in funders:
            fundername = f['funderName']
            funding_reference_identifier = f['fundingReferenceIdentifier']
            funding_reference_identifier_type = f['fundingReferenceIdentifierType']
            award_number = f['awardNumber']
            award_title = f['awardTitle']
            
            funder = Funder(fundername=fundername, funding_reference_identifier=funding_reference_identifier, funding_reference_identifier_type=funding_reference_identifier_type, award_number=award_number, award_title=award_title, sheet_id=sheet.id)
            funder.save()
        return True
    except Exception as e:
        print(repr(e))
        return False

def save_publication_sheet(publications, sheet):
    try:
        for p in publications:
            relatedidentifier = p['relatedIdentifier']
            relatedidentifiertype = p['relatedIdentifierType']
            pmcid = p['PMCID']
            relationtype = p['relationType']
            citation = p['citation']
            
            publication = Publication(relatedidentifier=relatedidentifier, relatedidentifiertype=relatedidentifiertype, pmcid=pmcid, relationtype=relationtype, citation=citation, sheet_id=sheet.id)
            publication.save()
        return True
    except Exception as e:
        print(repr(e))
        return False

def save_swc_sheet(swcs, sheet, saved_datasets):
    try:
        for s in swcs:
            data_set_id = saved_datasets[0].id
            tracingFile = s['tracingFile']
            sourceData = s['sourceData']
            sourceDataSample = s['sourceDataSample']
            sourceDataSubmission = s['sourceDataSubmission']
            coordinates = s['coordinates']
            coordinatesRegistration = s['coordinatesRegistration']
            brainRegion = s['brainRegion']
            brainRegionAtlas = s['brainRegionAtlas']
            brainRegionAtlasName = s['brainRegionAtlasName']
            brainRegionAxonalProjection = s['brainRegionAxonalProjection']
            brainRegionDendriticProjection = s['brainRegionDendriticProjection']
            neuronType = s['neuronType']
            segmentTags = s['segmentTags']
            proofreadingLevel = s['proofreadingLevel']
            notes = s['Notes']

            swc = SWC(tracingFile=tracingFile, sourceData=sourceData, sourceDataSample=sourceDataSample, sourceDataSubmission=sourceDataSubmission, coordinates=coordinates, coordinatesRegistration=coordinatesRegistration,  brainRegion=brainRegion, brainRegionAtlas=brainRegionAtlas, brainRegionAtlasName=brainRegionAtlasName, brainRegionAxonalProjection=brainRegionAxonalProjection, brainRegionDendriticProjection=brainRegionDendriticProjection, neuronType=neuronType, segmentTags=segmentTags, proofreadingLevel=proofreadingLevel, notes=notes, data_set_id=data_set_id,sheet_id=sheet.id)
            swc.save()

            swc_uuid = Mne.num_to_mne(swc.id)
            swc = SWC.objects.filter(id=swc.id).update(swc_uuid=swc_uuid)
        return True
    except Exception as e:
        print(repr(e))
        return False
    
def save_spatial_sheet(spatials, sheet, saved_datasets):
    # Many spatial rows : 1 dataset
    try:
        data_set_id = saved_datasets[0].id if isinstance(saved_datasets, list) else saved_datasets.id

        for s in spatials:
            dataavailability = s['DataAvailability']
            histologicalstainname = s['HistologicalStainName']
            nuclearstainname = s['NuclearStainName']
            probesetdoi = s['ProbeSetDOI']
            probesequencesdoi = s['ProbeSequencesDOI']
            lighttreatmenttime = s['LightTreatmentTime']
            lighttreatmenttimeunits = s['LightTreatmentTimeUnits']
            numbertargetedrna = s['NumberTargetedRNA']
            genepanelname = s['GenePanelName']
            platformname = s['PlatformName']
            machinename = s['MachineName']
            machinesoftwareversion = s['MachineSoftwareVersion']
            numberzsections = s['NumberZSections']
            segmentationmethod = s['SegmentationMethod']
            segmentationmodel = s['SegmentationModel']
            segmentationmethodversion = s['SegmentationMethodVersion']
            clusteringmethod = s['ClusteringMethod']
            labeltransfermethod = s['LabelTransferMethod']
            labeltransferreference = s['LabelTransferReference']
            nuclearimagetransform = s['NuclearImageTransform']
            histologicalimagetransform = s['HistologicalImageTransform']
            filtercriteria = s['FilterCriteria']
            xyzposition = s['XYZPosition']
            cellid = s['CellID']
            cellcentroidlocation = s['CellCentroidLocation']
            cellareavolume = s['CellAreaVolume']

            spatial = Spatial(
                dataavailability=dataavailability,
                histologicalstainname=histologicalstainname,
                nuclearstainname=nuclearstainname,
                probesetdoi=probesetdoi,
                probesequencesdoi=probesequencesdoi,
                lighttreatmenttime=lighttreatmenttime,
                lighttreatmenttimeunits=lighttreatmenttimeunits,
                numbertargetedrna=numbertargetedrna,
                genepanelname=genepanelname,
                platformname=platformname,
                machinename=machinename,
                machinesoftwareversion=machinesoftwareversion,
                numberzsections=numberzsections,
                segmentationmethod=segmentationmethod,
                segmentationmodel=segmentationmodel,
                segmentationmethodversion=segmentationmethodversion,
                clusteringmethod=clusteringmethod,
                labeltransfermethod=labeltransfermethod,
                labeltransferreference=labeltransferreference,
                nuclearimagetransform=nuclearimagetransform,
                histologicalimagetransform=histologicalimagetransform,
                filtercriteria=filtercriteria,
                xyzposition=xyzposition,
                cellid=cellid,
                cellcentroidlocation=cellcentroidlocation,
                cellareavolume=cellareavolume,
                data_set_id=data_set_id,
                sheet_id=sheet.id
            )
            spatial.save()
        return True
    except Exception as e:
        print(repr(e))
        return False

def save_instrument_sheet_method_1(instruments, sheet):
    # there should be 1 line in the instrument tab for methods 1, 2, 3
    try:
        for i in instruments:
            microscopetype = i['MicroscopeType']
            microscopemanufacturerandmodel = i['MicroscopeManufacturerAndModel']
            objectivename = i['ObjectiveName']
            objectiveimmersion = i['ObjectiveImmersion']
            objectivena = i['ObjectiveNA']
            objectivemagnification = i['ObjectiveMagnification']
            detectortype = i['DetectorType']
            detectormodel = i['DetectorModel']
            illuminationtypes = i['IlluminationTypes']
            illuminationwavelength = i['IlluminationWavelength']
            detectionwavelength = i['DetectionWavelength']
            sampletemperature = i['SampleTemperature']
            
            instrument = Instrument(microscopetype=microscopetype, microscopemanufacturerandmodel=microscopemanufacturerandmodel, objectivename=objectivename, objectiveimmersion=objectiveimmersion, objectivena=objectivena, objectivemagnification=objectivemagnification, detectortype=detectortype, detectormodel=detectormodel, illuminationtypes=illuminationtypes, illuminationwavelength=illuminationwavelength, detectionwavelength=detectionwavelength, sampletemperature=sampletemperature, sheet_id=sheet.id)
            instrument.save()
        return True
    except Exception as e:
        print(repr(e))
        return False

def save_instrument_sheet_method_2(instruments, sheet):
    # there should be 1 line in the instrument tab for methods 1, 2, 3
    try:
        for i in instruments:
            microscopetype = i['MicroscopeType']
            microscopemanufacturerandmodel = i['MicroscopeManufacturerAndModel']
            objectivename = i['ObjectiveName']
            objectiveimmersion = i['ObjectiveImmersion']
            objectivena = i['ObjectiveNA']
            objectivemagnification = i['ObjectiveMagnification']
            detectortype = i['DetectorType']
            detectormodel = i['DetectorModel']
            illuminationtypes = i['IlluminationTypes']
            illuminationwavelength = i['IlluminationWavelength']
            detectionwavelength = i['DetectionWavelength']
            sampletemperature = i['SampleTemperature']
            
            instrument = Instrument(microscopetype=microscopetype, microscopemanufacturerandmodel=microscopemanufacturerandmodel, objectivename=objectivename, objectiveimmersion=objectiveimmersion, objectivena=objectivena, objectivemagnification=objectivemagnification, detectortype=detectortype, detectormodel=detectormodel, illuminationtypes=illuminationtypes, illuminationwavelength=illuminationwavelength, detectionwavelength=detectionwavelength, sampletemperature=sampletemperature, sheet_id=sheet.id)
            instrument.save()
        return True
    except Exception as e:
        print(repr(e))
        return False

def save_instrument_sheet_method_3(instruments, sheet):
    # there should be 1 line in the instrument tab for methods 1, 2, 3
    try:
        for i in instruments:
            microscopetype = i['MicroscopeType']
            microscopemanufacturerandmodel = i['MicroscopeManufacturerAndModel']
            objectivename = i['ObjectiveName']
            objectiveimmersion = i['ObjectiveImmersion']
            objectivena = i['ObjectiveNA']
            objectivemagnification = i['ObjectiveMagnification']
            detectortype = i['DetectorType']
            detectormodel = i['DetectorModel']
            illuminationtypes = i['IlluminationTypes']
            illuminationwavelength = i['IlluminationWavelength']
            detectionwavelength = i['DetectionWavelength']
            sampletemperature = i['SampleTemperature']
            
            instrument = Instrument(microscopetype=microscopetype, microscopemanufacturerandmodel=microscopemanufacturerandmodel, objectivename=objectivename, objectiveimmersion=objectiveimmersion, objectivena=objectivena, objectivemagnification=objectivemagnification, detectortype=detectortype, detectormodel=detectormodel, illuminationtypes=illuminationtypes, illuminationwavelength=illuminationwavelength, detectionwavelength=detectionwavelength, sampletemperature=sampletemperature, sheet_id=sheet.id)
            instrument.save()
        return True
    except Exception as e:
        print(repr(e))
        return False

def save_instrument_sheet_method_4(instruments, sheet, saved_datasets):
    # instrument:dataset:images are 1:1. only 1 entry in specimen tab
    try:
        for d_index, d in enumerate(saved_datasets):
            data_set_id = d.id

            i = instruments[d_index]
            microscopetype = i['MicroscopeType']
            microscopemanufacturerandmodel = i['MicroscopeManufacturerAndModel']
            objectivename = i['ObjectiveName']
            objectiveimmersion = i['ObjectiveImmersion']
            objectivena = i['ObjectiveNA']
            objectivemagnification = i['ObjectiveMagnification']
            detectortype = i['DetectorType']
            detectormodel = i['DetectorModel']
            illuminationtypes = i['IlluminationTypes']
            illuminationwavelength = i['IlluminationWavelength']
            detectionwavelength = i['DetectionWavelength']
            sampletemperature = i['SampleTemperature']
            
            instrument = Instrument(microscopetype=microscopetype, microscopemanufacturerandmodel=microscopemanufacturerandmodel, objectivename=objectivename, objectiveimmersion=objectiveimmersion, objectivena=objectivena, objectivemagnification=objectivemagnification, detectortype=detectortype, detectormodel=detectormodel, illuminationtypes=illuminationtypes, illuminationwavelength=illuminationwavelength, detectionwavelength=detectionwavelength, sampletemperature=sampletemperature, data_set_id=data_set_id, sheet_id=sheet.id)
            instrument.save()
        return True
    except Exception as e:
        print(repr(e))
    return

def save_instrument_sheet_method_5(instruments, sheet, saved_datasets):
    # 1 instrument to many swc
    try:
        for d_index, d in enumerate(saved_datasets):
            data_set_id = d.id

            i = instruments[d_index]
            microscopetype = i['MicroscopeType']
            microscopemanufacturerandmodel = i['MicroscopeManufacturerAndModel']
            objectivename = i['ObjectiveName']
            objectiveimmersion = i['ObjectiveImmersion']
            objectivena = i['ObjectiveNA']
            objectivemagnification = i['ObjectiveMagnification']
            detectortype = i['DetectorType']
            detectormodel = i['DetectorModel']
            illuminationtypes = i['IlluminationTypes']
            illuminationwavelength = i['IlluminationWavelength']
            detectionwavelength = i['DetectionWavelength']
            sampletemperature = i['SampleTemperature']
            
            instrument = Instrument(microscopetype=microscopetype, microscopemanufacturerandmodel=microscopemanufacturerandmodel, objectivename=objectivename, objectiveimmersion=objectiveimmersion, objectivena=objectivena, objectivemagnification=objectivemagnification, detectortype=detectortype, detectormodel=detectormodel, illuminationtypes=illuminationtypes, illuminationwavelength=illuminationwavelength, detectionwavelength=detectionwavelength, sampletemperature=sampletemperature, data_set_id=data_set_id, sheet_id=sheet.id)
            instrument.save()
        return True
    except Exception as e:
        print(repr(e))
    return

def save_dataset_sheet_method_1_or_3(datasets, sheet):
    saved_datasets = []
    try:
        for d in datasets:
            bildirectory = d['BILDirectory']
            title = d['title']
            socialmedia = d['socialMedia']
            subject = d['subject']
            subjectscheme = d['Subjectscheme']
            rights = d['rights']
            rightsuri = d['rightsURI']
            rightsidentifier = d['rightsIdentifier']
            dataset_image = d['Image']
            generalmodality = d['GeneralModality']
            technique = d['Technique']
            other = d['Other']
            abstract = d['Abstract']
            methods = d['Methods']
            technicalinfo = d['TechnicalInfo']
            dataset = Dataset(bildirectory=bildirectory, title=title, socialmedia=socialmedia, subject=subject, subjectscheme=subjectscheme, rights=rights, rightsuri=rightsuri, rightsidentifier=rightsidentifier, dataset_image=dataset_image, generalmodality=generalmodality, technique=technique, other=other, abstract=abstract, methods=methods, technicalinfo=technicalinfo, sheet_id=sheet.id)
            dataset.save()
            saved_datasets.append(dataset)
        return saved_datasets
    except Exception as e:
        print(repr(e))
        return False

def save_dataset_sheet_method_2(datasets, sheet):
    # only 1 dataset row expected here
    try:
        for d in datasets:
            bildirectory = d['BILDirectory']
            title = d['title']
            socialmedia = d['socialMedia']
            subject = d['subject']
            subjectscheme = d['Subjectscheme']
            rights = d['rights']
            rightsuri = d['rightsURI']
            rightsidentifier = d['rightsIdentifier']
            dataset_image = d['Image']
            generalmodality = d['GeneralModality']
            technique = d['Technique']
            other = d['Other']
            abstract = d['Abstract']
            methods = d['Methods']
            technicalinfo = d['TechnicalInfo']

            dataset = Dataset(bildirectory=bildirectory, title=title, socialmedia=socialmedia, subject=subject, subjectscheme=subjectscheme, rights=rights, rightsuri=rightsuri, rightsidentifier=rightsidentifier, dataset_image=dataset_image, generalmodality=generalmodality, technique=technique, other=other, abstract=abstract, methods=methods, technicalinfo=technicalinfo, sheet_id=sheet.id)
            dataset.save()
            saved_datasets = dataset
        return saved_datasets
    except Exception as e:
        print(repr(e))
        return False

def save_dataset_sheet_method_4(datasets, sheet, specimen_object_method_4):
    specimen_ingest_method_4 = specimen_object_method_4

    saved_datasets = []
    try:
        for d in datasets:
            bildirectory = d['BILDirectory']
            title = d['title']
            socialmedia = d['socialMedia']
            subject = d['subject']
            subjectscheme = d['Subjectscheme']
            rights = d['rights']
            rightsuri = d['rightsURI']
            rightsidentifier = d['rightsIdentifier']
            dataset_image = d['Image']
            generalmodality = d['GeneralModality']
            technique = d['Technique']
            other = d['Other']
            abstract = d['Abstract']
            methods = d['Methods']
            technicalinfo = d['TechnicalInfo']

            dataset = Dataset(bildirectory=bildirectory, title=title, socialmedia=socialmedia, subject=subject, subjectscheme=subjectscheme, rights=rights, rightsuri=rightsuri, rightsidentifier=rightsidentifier, dataset_image=dataset_image, generalmodality=generalmodality, technique=technique, other=other, abstract=abstract, methods=methods, technicalinfo=technicalinfo, sheet_id=sheet.id, specimen_ingest_method_4=specimen_ingest_method_4)

            dataset.save()
            saved_datasets.append(dataset)

        return saved_datasets
    except Exception as e:
        print(repr(e))
        print(e)
        return False

def save_dataset_sheet_method_5(datasets, sheet, specimen_object_method_5):
    specimen_ingest_method_5 = specimen_object_method_5

    saved_datasets = []
    try:
        for d in datasets:
            bildirectory = d['BILDirectory']
            title = d['title']
            socialmedia = d['socialMedia']
            subject = d['subject']
            subjectscheme = d['Subjectscheme']
            rights = d['rights']
            rightsuri = d['rightsURI']
            rightsidentifier = d['rightsIdentifier']
            dataset_image = d['Image']
            generalmodality = d['GeneralModality']
            technique = d['Technique']
            other = d['Other']
            abstract = d['Abstract']
            methods = d['Methods']
            technicalinfo = d['TechnicalInfo']

            dataset = Dataset(bildirectory=bildirectory, title=title, socialmedia=socialmedia, subject=subject, subjectscheme=subjectscheme, rights=rights, rightsuri=rightsuri, rightsidentifier=rightsidentifier, dataset_image=dataset_image, generalmodality=generalmodality, technique=technique, other=other, abstract=abstract, methods=methods, technicalinfo=technicalinfo, sheet_id=sheet.id, specimen_ingest_method_4=specimen_ingest_method_5)

            dataset.save()
            saved_datasets.append(dataset)

        return saved_datasets
    except Exception as e:
        print(repr(e))
        print(e)
        return False

def save_specimen_sheet_method_1(specimen_set, sheet, saved_datasets):
    # multiple datasets, multple specimens, multiple images (1:1)
    # single instrument
    
    saved_specimens = []
    try:
        for d_index, d in enumerate(saved_datasets):
            data_set_id = d.id
            
            s = specimen_set[d_index]
            localid = s['LocalID']
            species = s['Species']
            ncbitaxonomy = s['NCBITaxonomy']
            age = s['Age']
            ageunit = s['Ageunit']
            sex = s['Sex']
            genotype = s['Genotype']
            organlocalid = s['OrganLocalID']
            organname = s['OrganName']
            samplelocalid = s['SampleLocalID']
            atlas = s['Atlas']
            locations = s['Locations']

            specimen_object = Specimen(localid=localid, species=species, ncbitaxonomy=ncbitaxonomy, age=age, ageunit=ageunit, sex=sex, genotype=genotype, organlocalid=organlocalid, organname=organname, samplelocalid=samplelocalid, atlas=atlas, locations=locations, sheet_id=sheet.id, data_set_id=data_set_id)
            specimen_object.save()
            saved_specimens.append(specimen_object)
        return saved_specimens
    except Exception as e:
        print(repr(e))
        return False

def save_specimen_sheet_method_2(specimen_set, sheet, saved_datasets):
    # multiple specimens, single dataset, single instrument, single image
    saved_specimens = []
    try:
        for s in specimen_set:
            data_set_id = saved_datasets.id

            localid = s['LocalID']
            species = s['Species']
            ncbitaxonomy = s['NCBITaxonomy']
            age = s['Age']
            ageunit = s['Ageunit']
            sex = s['Sex']
            genotype = s['Genotype']
            organlocalid = s['OrganLocalID']
            organname = s['OrganName']
            samplelocalid = s['SampleLocalID']
            atlas = s['Atlas']
            locations = s['Locations']

            specimen_object = Specimen(localid=localid, species=species, ncbitaxonomy=ncbitaxonomy, age=age, ageunit=ageunit, sex=sex, genotype=genotype, organlocalid=organlocalid, organname=organname, samplelocalid=samplelocalid, atlas=atlas, locations=locations, sheet_id=sheet.id, data_set_id=data_set_id)
            specimen_object.save()
            saved_specimens.append(specimen_object)
        return saved_specimens
    except Exception as e:
        print(repr(e))
        return False

def save_specimen_sheet_method_3(specimen_set, sheet, saved_datasets):
    # multiple datasets, multple specimens, multiple images (1:1)
    # single instrument
    
    saved_specimens = []
    try:
        for d_index, d in enumerate(saved_datasets):
            data_set_id = d.id
            
            s = specimen_set[d_index]
            localid = s['LocalID']
            species = s['Species']
            ncbitaxonomy = s['NCBITaxonomy']
            age = s['Age']
            ageunit = s['Ageunit']
            sex = s['Sex']
            genotype = s['Genotype']
            organlocalid = s['OrganLocalID']
            organname = s['OrganName']
            samplelocalid = s['SampleLocalID']
            atlas = s['Atlas']
            locations = s['Locations']

            specimen_object = Specimen(localid=localid, species=species, ncbitaxonomy=ncbitaxonomy, age=age, ageunit=ageunit, sex=sex, genotype=genotype, organlocalid=organlocalid, organname=organname, samplelocalid=samplelocalid, atlas=atlas, locations=locations, sheet_id=sheet.id, data_set_id=data_set_id)
            specimen_object.save()
            saved_specimens.append(specimen_object)
        return saved_specimens
    except Exception as e:
        print(repr(e))
        return False

def save_specimen_sheet_method_4(specimen_set, sheet):
    # multile datasets, multiple instruments, multiple images all 1:1
    # single specimen
    try:
        for s in specimen_set:
            localid = s['LocalID']
            species = s['Species']
            ncbitaxonomy = s['NCBITaxonomy']
            age = s['Age']
            ageunit = s['Ageunit']
            sex = s['Sex']
            genotype = s['Genotype']
            organlocalid = s['OrganLocalID']
            organname = s['OrganName']
            samplelocalid = s['SampleLocalID']
            atlas = s['Atlas']
            locations = s['Locations']

            specimen = Specimen(localid=localid, species=species, ncbitaxonomy=ncbitaxonomy, age=age, ageunit=ageunit, sex=sex, genotype=genotype, organlocalid=organlocalid, organname=organname, samplelocalid=samplelocalid, atlas=atlas, locations=locations, sheet_id=sheet.id)

            specimen.save()

            specimen_object_method_4 = specimen.id
            specimen_object_method_4 = int(specimen_object_method_4)
        return specimen_object_method_4
    except Exception as e:
        print(repr(e))
        return False

def save_specimen_sheet_method_5(specimen_set, sheet):
    # 1 datasets, 1 instruments, 0 images
    # 1 specimen
    try:
        for s in specimen_set:
            localid = s['LocalID']
            species = s['Species']
            ncbitaxonomy = s['NCBITaxonomy']
            age = s['Age']
            ageunit = s['Ageunit']
            sex = s['Sex']
            genotype = s['Genotype']
            organlocalid = s['OrganLocalID']
            organname = s['OrganName']
            samplelocalid = s['SampleLocalID']
            atlas = s['Atlas']
            locations = s['Locations']

            specimen = Specimen(localid=localid, species=species, ncbitaxonomy=ncbitaxonomy, age=age, ageunit=ageunit, sex=sex, genotype=genotype, organlocalid=organlocalid, organname=organname, samplelocalid=samplelocalid, atlas=atlas, locations=locations, sheet_id=sheet.id)

            specimen.save()

            specimen_object_method_5 = specimen.id
            specimen_object_method_5 = int(specimen_object_method_5)
        return specimen_object_method_5
    except Exception as e:
        print(repr(e))
        return False

def save_images_sheet_method_1(images, sheet, saved_datasets):
    # 1:1:1 dataset to image to specimen, only one row in instrument tab
    # images always are 1:1 with datasets
    try:
        for d_index, d in enumerate(saved_datasets):
            data_set_id = d.id

            i = images[d_index]
            xaxis = i['xAxis']
            obliquexdim1 = i['obliqueXdim1']
            obliquexdim2 = i['obliqueXdim2']
            obliquexdim3 = i['obliqueXdim3']
            yaxis = i['yAxis']
            obliqueydim1 = i['obliqueYdim1']
            obliqueydim2 = i['obliqueYdim2']
            obliqueydim3 = i['obliqueYdim3']
            zaxis = i['zAxis']
            obliquezdim1 = i['obliqueZdim1']
            obliquezdim2 = i['obliqueZdim2']
            obliquezdim3 = i['obliqueZdim3']
            landmarkname = i['landmarkName']
            landmarkx = i['landmarkX']
            landmarky = i['landmarkY']
            landmarkz = i['landmarkY']
            number = i['Number']
            displaycolor = i['displayColor']
            representation = i['Representation']
            flurophore = i['Flurophore']
            stepsizex = i['stepSizeX']
            stepsizey = i['stepSizeY']
            stepsizez = i['stepSizeZ']
            stepsizet = i['stepSizeT']
            channels = i['Channels']
            slices = i['Slices']
            z = i['z']
            xsize = i['Xsize']
            ysize = i['Ysize']
            zsize = i['Zsize']
            gbytes = i['Gbytes']
            files = i['Files']
            dimensionorder = i['DimensionOrder']
    
            image = Image(xaxis=xaxis, obliquexdim1=obliquexdim1, obliquexdim2=obliquexdim2, obliquexdim3=obliquexdim3, yaxis=yaxis, obliqueydim1=obliqueydim1, obliqueydim2=obliqueydim2, obliqueydim3=obliqueydim3, zaxis=zaxis, obliquezdim1=obliquezdim1, obliquezdim2=obliquezdim2, obliquezdim3=obliquezdim3,landmarkname=landmarkname, landmarkx=landmarkx, landmarky=landmarky, landmarkz=landmarkz, number=number, displaycolor=displaycolor, representation=representation, flurophore=flurophore, stepsizex=stepsizex, stepsizey=stepsizey, stepsizez=stepsizez, stepsizet=stepsizet, channels=channels, slices=slices, z=z, xsize=xsize, ysize=ysize, zsize=zsize, gbytes=gbytes, files=files, dimensionorder=dimensionorder, sheet_id=sheet.id, data_set_id=data_set_id)
            image.save()

        return True
    except Exception as e:
        print(repr(e))
        return False

def save_images_sheet_method_2(images, sheet, saved_datasets):
    # 1 dataset
    try:
        for i in images:
            data_set_id = saved_datasets.id

            xaxis = i['xAxis']
            obliquexdim1 = i['obliqueXdim1']
            obliquexdim2 = i['obliqueXdim2']
            obliquexdim3 = i['obliqueXdim3']
            yaxis = i['yAxis']
            obliqueydim1 = i['obliqueYdim1']
            obliqueydim2 = i['obliqueYdim2']
            obliqueydim3 = i['obliqueYdim3']
            zaxis = i['zAxis']
            obliquezdim1 = i['obliqueZdim1']
            obliquezdim2 = i['obliqueZdim2']
            obliquezdim3 = i['obliqueZdim3']
            landmarkname = i['landmarkName']
            landmarkx = i['landmarkX']
            landmarky = i['landmarkY']
            landmarkz = i['landmarkY']
            number = i['Number']
            displaycolor = i['displayColor']
            representation = i['Representation']
            flurophore = i['Flurophore']
            stepsizex = i['stepSizeX']
            stepsizey = i['stepSizeY']
            stepsizez = i['stepSizeZ']
            stepsizet = i['stepSizeT']
            channels = i['Channels']
            slices = i['Slices']
            z = i['z']
            xsize = i['Xsize']
            ysize = i['Ysize']
            zsize = i['Zsize']
            gbytes = i['Gbytes']
            files = i['Files']
            dimensionorder = i['DimensionOrder']
    
            image = Image(xaxis=xaxis, obliquexdim1=obliquexdim1, obliquexdim2=obliquexdim2, obliquexdim3=obliquexdim3, yaxis=yaxis, obliqueydim1=obliqueydim1, obliqueydim2=obliqueydim2, obliqueydim3=obliqueydim3, zaxis=zaxis, obliquezdim1=obliquezdim1, obliquezdim2=obliquezdim2, obliquezdim3=obliquezdim3,landmarkname=landmarkname, landmarkx=landmarkx, landmarky=landmarky, landmarkz=landmarkz, number=number, displaycolor=displaycolor, representation=representation, flurophore=flurophore, stepsizex=stepsizex, stepsizey=stepsizey, stepsizez=stepsizez, stepsizet=stepsizet, channels=channels, slices=slices, z=z, xsize=xsize, ysize=ysize, zsize=zsize, gbytes=gbytes, files=files, dimensionorder=dimensionorder, sheet_id=sheet.id, data_set_id=data_set_id)
            image.save()

        return True
    except Exception as e:
        print(repr(e))
        return False

def save_images_sheet_method_3(images, sheet, saved_datasets):
    # 1:1:1 dataset to image to specimen, only one row in instrument tab
    # images always are 1:1 with datasets
    try:
        for d_index, d in enumerate(saved_datasets):
            data_set_id = d.id

            i = images[d_index]
            xaxis = i['xAxis']
            obliquexdim1 = i['obliqueXdim1']
            obliquexdim2 = i['obliqueXdim2']
            obliquexdim3 = i['obliqueXdim3']
            yaxis = i['yAxis']
            obliqueydim1 = i['obliqueYdim1']
            obliqueydim2 = i['obliqueYdim2']
            obliqueydim3 = i['obliqueYdim3']
            zaxis = i['zAxis']
            obliquezdim1 = i['obliqueZdim1']
            obliquezdim2 = i['obliqueZdim2']
            obliquezdim3 = i['obliqueZdim3']
            landmarkname = i['landmarkName']
            landmarkx = i['landmarkX']
            landmarky = i['landmarkY']
            landmarkz = i['landmarkY']
            number = i['Number']
            displaycolor = i['displayColor']
            representation = i['Representation']
            flurophore = i['Flurophore']
            stepsizex = i['stepSizeX']
            stepsizey = i['stepSizeY']
            stepsizez = i['stepSizeZ']
            stepsizet = i['stepSizeT']
            channels = i['Channels']
            slices = i['Slices']
            z = i['z']
            xsize = i['Xsize']
            ysize = i['Ysize']
            zsize = i['Zsize']
            gbytes = i['Gbytes']
            files = i['Files']
            dimensionorder = i['DimensionOrder']
    
            image = Image(xaxis=xaxis, obliquexdim1=obliquexdim1, obliquexdim2=obliquexdim2, obliquexdim3=obliquexdim3, yaxis=yaxis, obliqueydim1=obliqueydim1, obliqueydim2=obliqueydim2, obliqueydim3=obliqueydim3, zaxis=zaxis, obliquezdim1=obliquezdim1, obliquezdim2=obliquezdim2, obliquezdim3=obliquezdim3,landmarkname=landmarkname, landmarkx=landmarkx, landmarky=landmarky, landmarkz=landmarkz, number=number, displaycolor=displaycolor, representation=representation, flurophore=flurophore, stepsizex=stepsizex, stepsizey=stepsizey, stepsizez=stepsizez, stepsizet=stepsizet, channels=channels, slices=slices, z=z, xsize=xsize, ysize=ysize, zsize=zsize, gbytes=gbytes, files=files, dimensionorder=dimensionorder, sheet_id=sheet.id, data_set_id=data_set_id)
            image.save()

        return True
    except Exception as e:
        print(repr(e))
        return False
    
def save_images_sheet_method_4(images, sheet, saved_datasets):
    # 1:1:1 dataset to image to specimen, only one row in instrument tab
    # images always are 1:1 with datasets
    try:
        for d_index, d in enumerate(saved_datasets):
            data_set_id = d.id

            i = images[d_index]
            xaxis = i['xAxis']
            obliquexdim1 = i['obliqueXdim1']
            obliquexdim2 = i['obliqueXdim2']
            obliquexdim3 = i['obliqueXdim3']
            yaxis = i['yAxis']
            obliqueydim1 = i['obliqueYdim1']
            obliqueydim2 = i['obliqueYdim2']
            obliqueydim3 = i['obliqueYdim3']
            zaxis = i['zAxis']
            obliquezdim1 = i['obliqueZdim1']
            obliquezdim2 = i['obliqueZdim2']
            obliquezdim3 = i['obliqueZdim3']
            landmarkname = i['landmarkName']
            landmarkx = i['landmarkX']
            landmarky = i['landmarkY']
            landmarkz = i['landmarkY']
            number = i['Number']
            displaycolor = i['displayColor']
            representation = i['Representation']
            flurophore = i['Flurophore']
            stepsizex = i['stepSizeX']
            stepsizey = i['stepSizeY']
            stepsizez = i['stepSizeZ']
            stepsizet = i['stepSizeT']
            channels = i['Channels']
            slices = i['Slices']
            z = i['z']
            xsize = i['Xsize']
            ysize = i['Ysize']
            zsize = i['Zsize']
            gbytes = i['Gbytes']
            files = i['Files']
            dimensionorder = i['DimensionOrder']
    
            image = Image(xaxis=xaxis, obliquexdim1=obliquexdim1, obliquexdim2=obliquexdim2, obliquexdim3=obliquexdim3, yaxis=yaxis, obliqueydim1=obliqueydim1, obliqueydim2=obliqueydim2, obliqueydim3=obliqueydim3, zaxis=zaxis, obliquezdim1=obliquezdim1, obliquezdim2=obliquezdim2, obliquezdim3=obliquezdim3,landmarkname=landmarkname, landmarkx=landmarkx, landmarky=landmarky, landmarkz=landmarkz, number=number, displaycolor=displaycolor, representation=representation, flurophore=flurophore, stepsizex=stepsizex, stepsizey=stepsizey, stepsizez=stepsizez, stepsizet=stepsizet, channels=channels, slices=slices, z=z, xsize=xsize, ysize=ysize, zsize=zsize, gbytes=gbytes, files=files, dimensionorder=dimensionorder, sheet_id=sheet.id, data_set_id=data_set_id)
            image.save()

        return True
    except Exception as e:
        print(repr(e))
        return False

def save_all_generic_sheets(contributors, funders, publications, sheet):
    try:
        if not save_contributors_sheet(contributors, sheet):
            return False
        if not save_funders_sheet(funders, sheet):
            return False
        if not save_publication_sheet(publications, sheet):
            return False
        return True
    except Exception as e:
        print(repr(e))
        return False

def save_all_sheets_method_1(instruments, specimen_set, images, datasets, sheet, contributors, funders, publications):
    # 1 dataset : 1 specimen : 1 image
    # only 1 single instrument row
    try:
        saved_datasets = save_dataset_sheet_method_1_or_3(datasets, sheet)
        if not saved_datasets:
            return False
        saved_instruments = save_instrument_sheet_method_1(instruments, sheet)
        if not saved_instruments:
            return False
        saved_specimens = save_specimen_sheet_method_1(specimen_set, sheet, saved_datasets)
        if not saved_specimens:
            return False
        saved_images = save_images_sheet_method_1(images, sheet, saved_datasets)
        if not saved_images:
            return False
        saved_generic = save_all_generic_sheets(contributors, funders, publications, sheet)
        if not saved_generic:
            return False
        return True
    except Exception as e:
        print(repr(e))
        return False
    

def save_all_sheets_method_2(instruments, specimen_set, images, datasets, sheet, contributors, funders, publications):
    # 1 dataset row, 1 instrument row, multiple specimens(have dataset FK)
    try:
        saved_datasets = save_dataset_sheet_method_2(datasets, sheet)
        if not saved_datasets:
            return False
        saved_instruments = save_instrument_sheet_method_2(instruments, sheet)
        if not saved_instruments:
            return False
        saved_specimens = save_specimen_sheet_method_2(specimen_set, sheet, saved_datasets)
        if not saved_specimens:
            return False
        saved_images = save_images_sheet_method_2(images, sheet, saved_datasets)
        if not saved_images:
            return False
        saved_generic = save_all_generic_sheets(contributors, funders, publications, sheet)
        if not saved_generic:
            return False
        return True
    except Exception as e:
        print(repr(e))
        return False

def save_all_sheets_method_3(instruments, specimen_set, images, datasets, sheet, contributors, funders, publications):
    # 1 dataset : 1 specimen : 1 image
    # only 1 single instrument row
    try:
        saved_datasets = save_dataset_sheet_method_1_or_3(datasets, sheet)
        if not saved_datasets:
            return False
        saved_instruments = save_instrument_sheet_method_3(instruments, sheet)
        if not saved_instruments:
            return False
        saved_specimens = save_specimen_sheet_method_3(specimen_set, sheet, saved_datasets)
        if not saved_specimens:
            return False
        saved_images = save_images_sheet_method_3(images, sheet, saved_datasets)
        if not saved_images:
            return False
        saved_generic = save_all_generic_sheets(contributors, funders, publications, sheet)
        if not saved_generic:
            return False
        return True
    except Exception as e:
        print(repr(e))
        return False

def save_all_sheets_method_4(instruments, specimen_set, images, datasets, sheet, contributors, funders, publications):
    # instrument:dataset:images are 1:1:1
    # 1 entry in specimen tab so each dataset gets the specimen id
    try:
        specimen_object_method_4 = save_specimen_sheet_method_4(specimen_set, sheet)
        if not specimen_object_method_4:
            return False
        saved_datasets = save_dataset_sheet_method_4(datasets, sheet, specimen_object_method_4)
        if not saved_datasets:
            return False
        saved_instruments = save_instrument_sheet_method_4(instruments, sheet, saved_datasets)
        if not saved_instruments:
            return False
        saved_images = save_images_sheet_method_4(images, sheet, saved_datasets)
        if not saved_images:
            return False
        saved_generic = save_all_generic_sheets(contributors, funders, publications, sheet)
        if not saved_generic:
            return False
        return True
    except Exception as e:
        print(repr(e))
        return False

def save_all_sheets_method_5(instruments, specimen_set, datasets, sheet, contributors, funders, publications, swcs):
    # if swc tab filled out we don't want images
    # many SWC : 1 dataset : 1 specimen : 1 instrument
    try:
        specimen_object_method_5 = save_specimen_sheet_method_5(specimen_set, sheet)
        if not specimen_object_method_5:
            return False
        saved_datasets = save_dataset_sheet_method_5(datasets, sheet, specimen_object_method_5)
        if not saved_datasets:
            return False
        saved_instruments = save_instrument_sheet_method_5(instruments, sheet, saved_datasets)
        if not saved_instruments:
            return False
        saved_swc = save_swc_sheet(swcs, sheet, saved_datasets)
        if not saved_swc:
            return False
        saved_generic = save_all_generic_sheets(contributors, funders, publications, sheet)
        if not saved_generic:
            return False
        return True
    except Exception as e:
        print(repr(e))
        return False

def save_all_sheets_method_6(
    instruments,
    specimen_set,
    datasets,
    sheet,
    contributors,
    funders,
    publications,
    spatials
):
    # Spatial Transcriptomics ingest method
    try:
        saved_datasets = save_dataset_sheet_method_2(datasets, sheet)
        if saved_datasets:
            saved_instruments = save_instrument_sheet_method_2(instruments, sheet)
            if saved_instruments:
                saved_specimens = save_specimen_sheet_method_2(specimen_set, sheet, saved_datasets)
                if saved_specimens:
                    saved_spatial = save_spatial_sheet(spatials, sheet, saved_datasets)
                    if saved_spatial:
                        saved_generic = save_all_generic_sheets(contributors, funders, publications, sheet)
                        if saved_generic:
                            return True
                        else:
                            return False
                    else:
                        return False
                else:
                    return False
            else:
                return False
        else:
            return False
    except Exception as e:
        print(repr(e))
        return False


def save_bil_ids(datasets, filename):
    workbook = xlrd.open_workbook(filename)
    dataset_sheet = workbook.sheet_by_name("Dataset")

    # Detect dev spreadsheet (BILDID column present)
    is_dev_spreadsheet = dataset_sheet.ncols > 15 and dataset_sheet.cell_type(3, 15) != xlrd.XL_CELL_EMPTY
    # ^ note: checking row 3 (0-based) hits header row that contains "BILDID"

    # Build directory -> dataset lookup from the datasets passed in
    # IMPORTANT: normalize trailing slashes to match spreadsheet style
    def norm_dir(s: str) -> str:
        s = (s or "").strip()
        # normalize trailing slash (your sheet has trailing slash)
        if s and not s.endswith("/"):
            s += "/"
        return s

    datasets_by_dir = {}
    for ds in datasets:
        d = norm_dir(getattr(ds, "bildirectory", None) or getattr(ds, "BILDirectory", None))
        if not d:
            continue
        datasets_by_dir[d] = ds

    validation_errors = []
    updates_to_apply = []

    if is_dev_spreadsheet:
        # Data rows start at row 6 (0-based) in this template (Excel row 7)
        start_row = 6

        seen_bil_ids = set()
        used_dataset_ids = set()

        # iterate spreadsheet rows, not datasets
        for row_index in range(start_row, dataset_sheet.nrows):
            spreadsheet_dir = norm_dir(dataset_sheet.cell_value(row_index, 0))
            bil_id_value = (dataset_sheet.cell_value(row_index, 15) or "").strip()

            # skip totally empty rows
            if not spreadsheet_dir and not bil_id_value:
                continue

            row_errors = []

            if not spreadsheet_dir:
                row_errors.append(f"Row {row_index + 1}: Missing BILDirectory (col A).")

            if not bil_id_value:
                row_errors.append(f"Row {row_index + 1}: Missing BIL_ID (col P).")

            if bil_id_value in seen_bil_ids:
                row_errors.append(f"Row {row_index + 1}: Duplicate BIL_ID in sheet: {bil_id_value}.")
            else:
                seen_bil_ids.add(bil_id_value)

            existing_bil_id = None
            if bil_id_value:
                try:
                    existing_bil_id = BIL_ID.objects.get(bil_id=bil_id_value)
                except BIL_ID.DoesNotExist:
                    row_errors.append(
                        f"Row {row_index + 1}: BIL_ID {bil_id_value} does not match any previous upload."
                    )

            # find the v2 dataset object by directory from the datasets list
            ds = None
            if spreadsheet_dir:
                ds = datasets_by_dir.get(spreadsheet_dir)
                if ds is None:
                    row_errors.append(
                        f"Row {row_index + 1}: No v2 Dataset found in this upload for directory {spreadsheet_dir}."
                    )

            # verify directory matches the directory tied to that BIL_ID in DB (v1 or v2)
            if existing_bil_id and spreadsheet_dir:
                if existing_bil_id.v2_ds_id:
                    db_dir = norm_dir(existing_bil_id.v2_ds_id.bildirectory)
                    if db_dir != spreadsheet_dir:
                        row_errors.append(
                            f"Row {row_index + 1}: Directory mismatch for BIL_ID {bil_id_value} (existing v2_ds_id)."
                        )
                elif existing_bil_id.v1_ds_id:
                    db_dir = norm_dir(existing_bil_id.v1_ds_id.r24_directory)
                    if db_dir != spreadsheet_dir:
                        row_errors.append(
                            f"Row {row_index + 1}: Directory mismatch for BIL_ID {bil_id_value} (existing v1_ds_id)."
                        )
                else:
                    row_errors.append(
                        f"Row {row_index + 1}: BIL_ID {bil_id_value} has no v1_ds_id or v2_ds_id."
                    )

            # prevent assigning the same dataset to multiple BIL_IDs
            if ds is not None:
                if ds.id in used_dataset_ids:
                    row_errors.append(
                        f"Row {row_index + 1}: The same v2 Dataset (id={ds.id}) is being assigned more than once."
                    )
                else:
                    used_dataset_ids.add(ds.id)

            if row_errors:
                validation_errors.extend(row_errors)
                continue

            # all good: queue update
            updates_to_apply.append({
                "bil_id": existing_bil_id,
                "v2_ds_id": ds,
                "metadata_version": 2
            })

        if validation_errors:
            return {"success": False, "errors": validation_errors}

        # Apply changes atomically (all-or-nothing)
        with transaction.atomic():
            for update in updates_to_apply:
                bil_id = update["bil_id"]
                bil_id.v2_ds_id = update["v2_ds_id"]
                bil_id.metadata_version = update["metadata_version"]
                bil_id.save()

        return None

    # Non-dev spreadsheet behavior (your existing logic)
    else:
        for dataset in datasets:
            bil_id = BIL_ID(v2_ds_id=dataset, metadata_version=2, doi=False)
            bil_id.save()
            saved_bil_id = BIL_ID.objects.get(v2_ds_id=dataset.id)
            mne_id = Mne.dataset_num_to_mne(saved_bil_id.id)
            saved_bil_id.bil_id = mne_id
            saved_bil_id.save()

        return None

def save_specimen_ids(specimens):
    """
    This function iterates through the provided list of specimens, generates and saves bil_specimen_IDs
    using the bil_specimen_ID model. It also associates an MNE ID with each bil_specimen_ID and saves the updated
    bil_specimen_ID object in the database.
    """
    for specimen in specimens:
        #create placeholder for BIL_specimen_ID
        bil_spc_id = BIL_Specimen_ID(specimen_id = specimen)
        bil_spc_id.save()
        #grab the just created database ID and generate an mne id
        saved_bil_spc_id = BIL_Specimen_ID.objects.get(specimen_id = specimen.id)
        mne_id = Mne.specimen_num_to_mne(saved_bil_spc_id.id)
        saved_bil_spc_id.bil_spc_id = mne_id
        #final save
        saved_bil_spc_id.save()
    return

def save_instrument_ids(instruments):
    """
    This function iterates through the provided list of instruments, generates and saves bil_instrument_IDs
    using the bil_instrument_ID model. It also associates an MNE ID with each bil_instrument_ID and saves the updated
    bil_instrument_ID object in the database.
    """
    for instrument in instruments:
        #create placeholder for BIL_instrument_ID
        bil_ins_id = BIL_Instrument_ID(instrument_id = instrument)
        bil_ins_id.save()
        #grab the just created database ID and generate an mne id
        saved_bil_ins_id = BIL_Instrument_ID.objects.get(instrument_id = instrument.id)
        mne_id = Mne.instrument_num_to_mne(saved_bil_ins_id.id)
        saved_bil_ins_id.bil_ins_id = mne_id
        #final save
        saved_bil_ins_id.save()
    return

def save_project_id(project):
    #create placeholder for BIL_instrument_ID
    bil_prj_id = BIL_Project_ID(project_id = project)
    bil_prj_id.save()
    #grab the just created database ID and generate an mne id
    saved_bil_prj_id = BIL_Project_ID.objects.get(project_id = project.id)
    mne_id = Mne.project_num_to_mne(saved_bil_prj_id.id)
    saved_bil_prj_id.bil_prj_id = mne_id
    #final save
    saved_bil_prj_id.save()
    return

def metadata_version_check(filename):
    version1 = False
    workbook=xlrd.open_workbook(filename)
    try:
        if workbook.sheet_by_name('README'):
            version1 = False
    except:
        version1 = True
    return version1

def check_all_sheets(filename, ingest_method):
    """Run all sheet validators and return a structured error map.

    Returns a dict mapping "SheetName::row::col" -> [message, ...].
    An empty dict means no errors were found.
    """
    workbook = xlrd.open_workbook(filename)
    sheetnames = workbook.sheet_names()
    error_map = {}

    def merge(sheet_name, errs):
        for e in errs:
            key = f"{sheet_name}::{e['row']}::{e['col']}"
            error_map.setdefault(key, []).append(e['message'])

    merge('Contributors', check_contributors_sheet(filename))
    merge('Funders', check_funders_sheet(filename))
    merge('Publication', check_publication_sheet(filename))
    merge('Instrument', check_instrument_sheet(filename))
    merge('Dataset', check_dataset_sheet(filename))
    merge('Specimen', check_specimen_sheet(filename))

    if ingest_method != 'ingest_5':
        merge('Image', check_image_sheet(filename))

    if ingest_method == 'ingest_5':
        merge('SWC', check_swc_sheet(filename))

    if ingest_method in ('ingest_1', 'ingest_2') and 'Spatial' in sheetnames:
        merge('Spatial', check_spatial_sheet(filename))

    return error_map

def make_ingest_jwt(sub: str = "django") -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "iss": settings.DOI_JWT_ISSUER,       # must match FastAPI JWT_ISSUER
        "aud": settings.DOI_JWT_AUDIENCE,     # must match FastAPI JWT_AUDIENCE
        "iat": now,
        "exp": now + 60,
    }
    return jwt.encode(payload, settings.DOI_JWT_SECRET, algorithm="HS256")


def build_canonical_record_from_bil(bil_record: BIL_ID, doi: str) -> dict:
    """
    Minimal CanonicalRecord that satisfies your FastAPI schema.
    The ONLY hard requirement is Dataset.DOI (or Dataset.doi).
    Fill the rest as you like (or leave empty) and iterate later.
    """
    ds = bil_record.v2_ds_id

    return {
        "Metadata": {},
        "Submission": {},
        "Contributors": [],
        "Funders": [],
        "Specimen": {},
        "Dataset": {
            "DOI": doi,
            "Title": getattr(ds, "title", "") if ds else "",
            "Directory": getattr(ds, "bildirectory", "") if ds else "",
        },
        "Image": {},
    }

def doi_api(request):
    print(f"Received request: {request.method}")

    try:
        data = json.loads(request.body)
        print(f"Received payload: {data}")
        bil_id = data.get("bildid")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format"}, status=400)

    if not bil_id:
        return JsonResponse({"error": "No BIL_ID provided"}, status=400)

    print(f"Got BIL_ID: {bil_id}")

    # 1) Call DOI mint API (your existing doi-api service)
    datacite_url = getattr(settings, "DATACITE_DOI_API_URL", "http://127.0.0.1:8094/draft")
    payload = {"bildid": bil_id, "action": "draft"}
    headers = {"Content-Type": "application/json"}

    try:
        print(f"Sending payload to DOI API: {json.dumps(payload, indent=2)}")
        response = requests.post(datacite_url, json=payload, headers=headers, timeout=45)
        print(f"DOI API Response: {response.status_code} - {response.text}")

        if response.status_code != 201:
            return JsonResponse({"error": response.text}, status=response.status_code)

        # DOI minted successfully
        bil_record = get_object_or_404(BIL_ID, bil_id=bil_id)

        # Determine DOI string (best: parse from DOI API response if it returns it)
        try:
            mint_json = response.json()
        except Exception:
            mint_json = {}

        # If your doi-api returns it, use it; else fallback to your known pattern
        minted_doi = mint_json.get("doi") or f"10.80303/{bil_id}"

        # Update local state (you currently store a boolean on BIL_ID; keep if you want)
        bil_record.doi = True
        bil_record.save(update_fields=["doi"])
        print(f"Updated BIL_ID {bil_id} as DOI=True")

        # Build DOI URL (test resolver example you used)
        doi_url = mint_json.get("doi_url") or f"https://doi.test.datacite.org/dois/10.80303%2F{bil_id}"

        # 2) Call your FastAPI Mongo ingest service
        mongo_ingest_url = getattr(settings, "MONGO_INGEST_API_URL", "http://127.0.0.1:8000/v1/doi-datasets")
        canonical_record = build_canonical_record_from_bil(bil_record, minted_doi)

        token = make_ingest_jwt(sub=request.user.get_username() or "django")
        ingest_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        print(f"Sending canonical record to Mongo ingest API: {mongo_ingest_url}")
        ingest_resp = requests.post(mongo_ingest_url, json=canonical_record, headers=ingest_headers, timeout=45)
        print(f"Mongo ingest response: {ingest_resp.status_code} - {ingest_resp.text}")

        if ingest_resp.status_code >= 400:
            # Important: DOI is already minted; don't "undo" it.
            # Return an error so you notice + can retry ingest later.
            return JsonResponse(
                {
                    "error": "DOI minted, but Mongo ingest failed",
                    "doi_url": doi_url,
                    "doi": minted_doi,
                    "ingest_status": "failed",
                    "ingest_error": ingest_resp.text,
                },
                status=502,
            )

        ingest_json = ingest_resp.json() if ingest_resp.content else {}
        return JsonResponse(
            {
                "success": True,
                "doi_url": doi_url,
                "doi": minted_doi,
                "ingest": ingest_json,  # {"status": "inserted"|"noop_exists", "doi": ...}
            },
            status=201,
        )

    except requests.exceptions.RequestException as e:
        print(f"Request Error: {str(e)}")
        return JsonResponse({"error": f"Request failed: {str(e)}"}, status=500)
    
@login_required
@login_required
def metadata_error_view(request, associated_collection):
    """Display spreadsheet validation errors with per-cell highlighting."""
    import json as _json
    error_map = request.session.pop('metadata_errors', None)
    filename = request.session.pop('metadata_error_filename', None)

    if not error_map or not filename:
        return redirect('ingest:descriptive_metadata_upload', associated_collection=associated_collection)

    workbook = xlrd.open_workbook(filename)
    sheets = {}
    for sheet_name in workbook.sheet_names():
        ws = workbook.sheet_by_name(sheet_name)
        rows = []
        for row_idx in range(ws.nrows):
            row = []
            for col_idx in range(ws.ncols):
                cell = ws.cell(row_idx, col_idx)
                row.append(str(cell.value) if cell.value != '' else '')
            rows.append(row)
        sheets[sheet_name] = rows

    return render(request, 'ingest/metadata_error_view.html', {
        'sheets': sheets,
        'error_map_json': _json.dumps(error_map),
        'associated_collection': associated_collection,
    })


def _report_bil_id_errors(request, result):
    """Attach save_bil_ids error(s) to the request messages framework.

    save_bil_ids returns None on success, a dict {"success": False, "errors": [...]}
    for dev-spreadsheet validation failures, or a plain string for other errors.
    """
    if isinstance(result, dict):
        for err in result.get('errors', []):
            messages.error(request, err)
    else:
        messages.error(request, str(result))


@login_required
def descriptive_metadata_upload(request, associated_collection):
    current_user = request.user
    try:
        people = People.objects.get(auth_user_id_id = current_user.id)
        project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    except: 
        messages.info(request, 'Error: Your account is likely not fully set up. Follow along with your Sign Up ticket on bil-support and provide the appropriate Grant Name and Number to the Project you will be submitting for. If you have already done so, kindly nudge us to complete your account creation.')
        return redirect('/')
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False    
    """ Upload a spreadsheet containing image metadata information. """
    # The POST. A user has selected a file and associated collection to upload.
    if request.method == 'POST' and request.FILES['spreadsheet_file']:
        #form = UploadForm(request.POST)

        ingest_method = request.POST.get('ingest_method', False)
	
        #if form.is_valid():
        associated_collection = Collection.objects.get(id = associated_collection)

        # for production
        #datapath = associated_collection.data_path.replace("/lz/","/etc/")
            
            # for development on vm
        #datapath = '/Users/luketuite/shared_bil_dev' 

        # for development locally
        datapath = '/Users/luketuite/shared_bil_dev' 
        
        spreadsheet_file = request.FILES['spreadsheet_file']

        fs = FileSystemStorage(location=datapath)
        unique_name = fs.save(spreadsheet_file.name, spreadsheet_file)
        filename = os.path.join(datapath, unique_name)
        workbook = xlrd.open_workbook(filename)
        has_spatial = 'Spatial' in workbook.sheet_names()

        version1 = metadata_version_check(filename)
        
        # using old metadata model for any old submissions (will eventually be deprecated)
        if version1 == True:
            error = upload_descriptive_spreadsheet(filename, associated_collection, request)
            if error:
                return redirect('ingest:descriptive_metadata_upload', associated_collection=associated_collection.id)
            else:         
                return redirect('ingest:descriptive_metadata_list')
        
        # using new metadata model
        elif version1 == False:
            error_map = check_all_sheets(filename, ingest_method)
            if error_map:
                request.session['metadata_errors'] = error_map
                request.session['metadata_error_filename'] = filename
                return redirect('ingest:metadata_error_view', associated_collection=associated_collection.id)

            else:
                saved = False
                collection = Collection.objects.get(name=associated_collection.name)
                contributors = ingest_contributors_sheet(filename)
                funders = ingest_funders_sheet(filename)
                publications = ingest_publication_sheet(filename)
                instruments = ingest_instrument_sheet(filename)
                datasets = ingest_dataset_sheet(filename)
                specimen_set = ingest_specimen_sheet(filename)
                images = ingest_image_sheet(filename)
                swcs = ingest_swc_sheet(filename)
                # Only ingest spatial if Spatial sheet exists AND ingest method is 1 or 2
                if has_spatial and ingest_method in ('ingest_1', 'ingest_2'):
                    spatials = ingest_spatial_sheet(filename)
                else:
                    spatials = []

                # choose save method depending on ingest_method value from radio button
                if ingest_method == 'ingest_1':
                    sheet = save_sheet_row(ingest_method, filename, collection)
                    saved = save_all_sheets_method_1(instruments, specimen_set, images, datasets, sheet, contributors, funders, publications)
                    if has_spatial:
                        ingested_datasets = list(Dataset.objects.filter(sheet=sheet))
                        save_spatial_sheet(spatials, sheet, ingested_datasets)
                    ingested_datasets = Dataset.objects.filter(sheet=sheet)
                    ingested_specimens = Specimen.objects.filter(sheet=sheet)
                    bil_id_result = save_bil_ids(ingested_datasets, filename)
                    if bil_id_result is not None:
                        _report_bil_id_errors(request, bil_id_result)
                        return redirect('ingest:descriptive_metadata_upload', associated_collection=associated_collection.id)
                    save_specimen_ids(ingested_specimens)
                elif ingest_method == 'ingest_2':
                    sheet = save_sheet_row(ingest_method, filename, collection)
                    saved = save_all_sheets_method_2(instruments, specimen_set, images, datasets, sheet, contributors, funders, publications)
                    if has_spatial:
                        ingested_datasets = list(Dataset.objects.filter(sheet=sheet))
                        save_spatial_sheet(spatials, sheet, ingested_datasets)
                    ingested_datasets = Dataset.objects.filter(sheet=sheet)
                    ingested_specimens = Specimen.objects.filter(sheet=sheet)
                    bil_id_result = save_bil_ids(ingested_datasets, filename)
                    if bil_id_result is not None:
                        _report_bil_id_errors(request, bil_id_result)
                        return redirect('ingest:descriptive_metadata_upload', associated_collection=associated_collection.id)
                    save_specimen_ids(ingested_specimens)
                elif ingest_method == 'ingest_3':
                    sheet = save_sheet_row(ingest_method, filename, collection)
                    saved = save_all_sheets_method_3(instruments, specimen_set, images, datasets, sheet, contributors, funders, publications)
                    ingested_datasets = Dataset.objects.filter(sheet=sheet)
                    ingested_specimens = Specimen.objects.filter(sheet=sheet)
                    bil_id_result = save_bil_ids(ingested_datasets, filename)
                    if bil_id_result is not None:
                        _report_bil_id_errors(request, bil_id_result)
                        return redirect('ingest:descriptive_metadata_upload', associated_collection=associated_collection.id)
                    save_specimen_ids(ingested_specimens)
                elif ingest_method == 'ingest_4':
                    sheet = save_sheet_row(ingest_method, filename, collection)
                    saved = save_all_sheets_method_4(instruments, specimen_set, images, datasets, sheet, contributors, funders, publications)
                    ingested_datasets = Dataset.objects.filter(sheet=sheet)
                    ingested_specimens = Specimen.objects.filter(sheet=sheet)
                    bil_id_result = save_bil_ids(ingested_datasets, filename)
                    if bil_id_result is not None:
                        _report_bil_id_errors(request, bil_id_result)
                        return redirect('ingest:descriptive_metadata_upload', associated_collection=associated_collection.id)
                    save_specimen_ids(ingested_specimens)
                elif ingest_method == 'ingest_5':
                    sheet = save_sheet_row(ingest_method, filename, collection)
                    saved = save_all_sheets_method_5(instruments, specimen_set, datasets, sheet, contributors, funders, publications, swcs)
                    ingested_datasets = Dataset.objects.filter(sheet=sheet)
                    ingested_specimens = Specimen.objects.filter(sheet=sheet)
                    bil_id_result = save_bil_ids(ingested_datasets, filename)
                    if bil_id_result is not None:
                        _report_bil_id_errors(request, bil_id_result)
                        return redirect('ingest:descriptive_metadata_upload', associated_collection=associated_collection.id)
                    save_specimen_ids(ingested_specimens)
                else:
                    messages.error(request, 'You must choose a value from "Step 2 of 3: What does your data look like?"')
                    return redirect('ingest:descriptive_metadata_upload', associated_collection=associated_collection.id)

                if saved:
                    saved_datasets = Dataset.objects.filter(sheet_id=sheet.id).all()
                    for dataset in saved_datasets:
                        time = datetime.now()
                        event = DatasetEventsLog(dataset_id=dataset, collection_id=collection, project_id_id=collection.project_id, notes='', timestamp=time, event_type='uploaded')
                        event.save()
                    messages.success(request, 'Descriptive Metadata successfully uploaded!!')
                    if ProjectConsortium.objects.filter(project=associated_collection.project, consortium__short_name='BICAN').exists():
                        return redirect('ingest:bican_id_upload', sheet_id=sheet.id)
                    else:
                        return redirect('ingest:descriptive_metadata_list')
                else:
                    messages.error(request, f'There was an error saving your metadata. Please contact BIL Support with Error Code: {sheet.id}')
                    return redirect('ingest:descriptive_metadata_upload', associated_collection=associated_collection.id)


    # This is the GET (just show the metadata upload page)
    else:
        user = request.user
        #form = UploadForm()
        # Only let a user associate metadata with an unlocked collection that they own
        #form.fields['associated_collection'].queryset = Collection.objects.filter(
        #    locked=False, user=request.user)
        #collections = form.fields['associated_collection'].queryset
    #this_collection = Collection.objects.filter(id = associated_collection)
    #projCons = ProjectConsortium.objects.filter(project=this_collection.project)
    #if projCons.consortium == 'BICAN':
    
    collections = Collection.objects.filter(locked=False, user=request.user)
    return render(request, 'ingest/descriptive_metadata_upload.html',{'pi':pi, 'collections':collections, 'associated_collection': associated_collection})

WHITELIST_FIELDS = {
    "data",
    "category",
    "record",
    "has_parent",
    "has_parent_identifier",
    "has_parent_identifiers",
    "donor_nhash_id",
    "repository",
    "donor_source",
    "donor_species",
    "hemisphere",
    "left_hemisphere_preparation",
    "right_hemisphere_preparation",
    "rin",
    "rine",
    "ph",
    "brain_weight",
    "weighed_type",
    "postmortem_mri_type",
    "tissue_type",
    "brain_subdivision",
    "slab_hemisphere",
    "number_of_slabs",
    "thickness",
    "anatomical_direction_top_btm",
    "anatomical_direction_left_right",
    "anatomical_direction_across_slabs",
    "local_slab_ids",
    "visible_slab_face",
    "slab_nhash_id",
    "tissue_nhash_id",
    "species",
    "project_identifier",
    "structure",
    "dissociated_cell_sample_nhash_id",
    "dissociated_cell_sample_cell_label_barcode",
    "dissociated_cell_sample_cell_prep_type",
    "enriched_cell_sample_nhash_id",
    "enriched_cell_sample_cell_label_barcode",
    "barcoded_cell_sample_nhash_id",
    "barcoded_cell_sample_number_of_expected_cells",
    "barcoded_cell_input_quantity_count",
    "barcoded_cell_sample_technique",
    "amplified_cdna_nhash_id",
    "library_nhash_id",
    "library_technique",
    "library_r1_r2_index",
    "library_source_type",
    "library_pool_nhash_id",
    "library_pool_tube_barcode",
    "sequencing_center_id",
    "tissue_nhash_ids",
    "consent_status",
    "left_hemisphere_prep_2",
    "right_hemisphere_prep_2",
    "patched_cell_structure",
    "tissue_brain_subdivision",
    "tissue_brain_hemisphere",
    "section_sample_ordinal",
    "section_sample_thickness",
    "section_nhash_id",
    "access_level",
    "data_use_limitation",
    "disease_specification",
    "irb_approval_required",
    "publication_required",
    "collaboration_required",
    "not_for_profit",
    "methods",
    "genetic_study_only",
    "number_of_reads",
    "sequencing_saturation",
    "fraction_of_unique_reads_mapped_to_genome",
    "fraction_of_unique_and_multiple_reads_mapped_to_genome",
    "fraction_of_reads_with_Q30_bases_in_rna",
    "fraction_of_reads_with_Q30_bases_in_cb_and_umi",
    "fraction_of_reads_with_valid_barcodes",
    "reads_mapped_antisense_to_gene",
    "reads_mapped_confidently_exonic",
    "reads_mapped_confidently_to_genome",
    "reads_mapped_confidently_to_intronic_regions",
    "reads_mapped_confidently_to_transcriptome",
    "estimated_cells",
    "umis_in_cells",
    "mean_umi_per_cell",
    "median_umi_per_cell",
    "unique_reads_in_cells_mapped_to_gene",
    "fraction_of_unique_reads_in_cells",
    "mean_reads_per_cell",
    "median_reads_per_cell",
    "mean_gene_per_cell",
    "median_gene_per_cell",
    "total_genes_unique_detected",
    "percent_target",
    "percent_intronic_reads",
    "keeper_mean_reads_per_cell",
    "keeper_median_genes",
    "keeper_cells",
    "percent_keeper",
    "percent_usable",
    "frac_tso",
    "percent_doublets",
    "sequenced_reads",
    "sequenced_read_pairs",
    "fraction_valid_barcode",
    "fraction_q30_bases_in_read_1",
    "fraction_q30_bases_in_read_2",
    "number_of_cells",
    "mean_raw_read_pairs_per_cell",
    "median_high_quality_fragments_per_cell",
    "fraction_of_high_quality_fragments_in_cells",
    "fraction_of_transposition_events_in_peaks_in_cells",
    "fraction_duplicates",
    "fraction_confidently_mapped",
    "fraction_unmapped",
    "fraction_nonnuclear",
    "fraction_fragment_in_nucleosome_free_region",
    "fraction_fragment_flanking_single_nucleosome",
    "tss_enrichment_score",
    "fraction_of_high_quality_fragments_overlapping_tss",
    "number_of_peaks",
    "fraction_of_genome_in_peaks",
    "fraction_of_high_quality_fragments_overlapping_peaks",
    "atac_percent_target",
    "tissue_sample_type",
    "tissue_structure_acronym",
    "library_aliquot_fastq_file_size_in_tb",
    "library_pool_sequencing_instrument",
    "library_pool_flowcell_type",
    "library_pool_fastq_submission_id",
    "gsr_controlled_access",
    "donor_project",
    "slab_project",
    "tissue_project",
    "section_project",
    "dissociated_cell_sample_project",
    "enriched_cell_sample_project",
    "barcoded_cell_sample_project",
    "amplified_cdna_project",
    "library_project",
    "library_aliquot_project",
    "library_pool_projects",
    "donor_labs",
    "tissue_lab",
    "section_lab",
    "dissociated_cell_sample_lab",
    "enriched_cell_sample_lab",
    "barcoded_cell_sample_lab",
    "amplified_cdna_lab",
    "library_lab",
    "library_aliquot_lab",
    "library_pool_labs",
    "alignment_qc_status",
    "nemo_pool_bucket",
    "nemo_aliquot_fastq_public_url",
    "nemo_aliquot_fastq_gcp_url",
    "ic_form_nhash_id",
    "roi_type",
    "slab_brain_subdivision",
    "slab_thickness",
    "slab_visible_slab_face",
}

NHASH_KEY_RE = re.compile(r"^(TI|RI|SL|DO|SC)-", re.IGNORECASE)

def normalize_key(key: str) -> str:
    key = str(key).lower().strip()
    key = re.sub(r"[^\w\s]", " ", key)   # punctuation -> space
    key = re.sub(r"\s+", "_", key)       # whitespace -> underscore
    return key

NORMALIZED_WHITELIST = {normalize_key(k) for k in WHITELIST_FIELDS}

def whitelist_filter(obj, *, keep_all_keys=False):
    """
    - Always preserves the top-level 'data' container
    - Preserves NHASH IDs inside data (TI-..., RI-..., etc.)
    - Applies whitelist only inside each NHASH record dict
    """
    if isinstance(obj, dict):
        cleaned = {}

        for k, v in obj.items():
            nk = normalize_key(k)

            # 1) Always preserve the 'data' container (template requires it)
            if nk == "data":
                # Under data: keep NHASH IDs, but filter inside each record
                if isinstance(v, dict):
                    data_cleaned = {}
                    for nhash_id, record in v.items():
                        # NHASH ID keys like TI-..., RI-...
                        if NHASH_KEY_RE.match(str(nhash_id)):
                            data_cleaned[nhash_id] = whitelist_filter(record, keep_all_keys=False)
                        else:
                            # If there are non-NHASH keys under data, you can drop them
                            # or keep them if you want:
                            # data_cleaned[nhash_id] = whitelist_filter(record, keep_all_keys=False)
                            pass
                    cleaned[k] = data_cleaned
                else:
                    cleaned[k] = whitelist_filter(v, keep_all_keys=False)
                continue

            # 2) Inside a record dict: only keep whitelisted fields
            if keep_all_keys or nk in NORMALIZED_WHITELIST:
                cleaned[k] = whitelist_filter(v, keep_all_keys=False)

        return cleaned

    if isinstance(obj, list):
        return [whitelist_filter(item, keep_all_keys=keep_all_keys) for item in obj]

    return obj

def bican_id_upload(request, sheet_id):
    if request.method == 'GET':
        specimens = Specimen.objects.filter(sheet_id=sheet_id)
        context = {'sheet_id': sheet_id, 'specimens': specimens}
        
        # Get error message from query parameter if exists
        error_message = request.GET.get('error_message', None)
        if error_message:
            messages.error(request, error_message)
        
        form_data = request.POST.copy() if request.method == 'POST' else None
        context['form_data'] = form_data

        return render(request, 'ingest/specimen_bican.html', context)
    else:
        sheet_id = sheet_id
        specimens = Specimen.objects.filter(sheet_id=sheet_id)
        context = {'sheet_id': sheet_id, 'specimens': specimens}
    
    return render(request, 'ingest/specimen_bican.html', context)

def specimen_bican(request, sheet_id):
    # Retrieve Specimen Local IDs corresponding to the uploaded sheet
    specimens = Specimen.objects.filter(sheet_id=sheet_id)

    # Create an empty DataFrame
    df_list = []

    # Iterate through each Specimen object and add it to the DataFrame
    for specimen in specimens:
        df_list.append(pd.DataFrame({'Specimen ID': [specimen.id], 'Specimen Local ID': [specimen.localid], 'BICAN ID': ['']}))

    # Concatenate the DataFrames row-wise
    df = pd.concat(df_list, ignore_index=True)

    # Create a BytesIO object to write the Excel file to
    excel_file = io.BytesIO()

    # Write the DataFrame to an Excel file
    df.to_excel(excel_file, index=False)

    # Rewind the buffer's position to the start
    excel_file.seek(0)

    # Set the appropriate content type for Excel files
    response = HttpResponse(excel_file.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    # Set the filename for the download
    response['Content-Disposition'] = 'attachment; filename=specimen_local_and_bican_ids.xlsx'

    return response

def save_bican_spreadsheet(request):
    if request.method == 'POST':
        uploaded_file = request.FILES['file']
        sheet_id = request.POST.get('sheet_id')
        if uploaded_file.name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file)

            specimen_id_list = []
            specimen_list = []
            nhash_info_list = []
            error_messages = []

            for _, row in df.iterrows():
                spec_id = row['Specimen ID']
                bican_id = row['BICAN ID']

                spec_bil_id, local_name = process_specimen_id(spec_id)
                specimen_id_list.append(spec_bil_id)
                specimen_list.append(local_name)

                nhash_info, error_message = retrieve_nhash_info(bican_id)
                if error_message:
                    error_messages.append(error_message)
                    continue
                nhash_info_list.append(nhash_info)

            if error_messages:
                # Handle errors here
                return HttpResponseRedirect(reverse('ingest:bican_id_upload', args=[sheet_id]) + f'?error_message={error_messages[0]}')

            extracted_ids = []
            for nhash_info in nhash_info_list:
                ids = extract_ids(nhash_info)  # Extract IDs for each nhash_info individually
                extracted_ids.append(ids)
            processed_ids = specimen_list_mapping(extracted_ids, specimen_id_list)  # Assuming this function exists
            processed_ids_json = json.dumps(processed_ids)
            nhash_info_list = [whitelist_filter(x) for x in nhash_info_list]
            nhash_specimen_list = zip(nhash_info_list, specimen_list)

            return render(request, 'ingest/nhash_id_confirm.html', {
                'nhash_specimen_list': nhash_specimen_list,
                'processed_ids_json': processed_ids_json
            })

        else:
            # Handle case where uploaded file is not an Excel file
            error_message = 'An Error Has Occurred, please upload a valid .xlsx Spreadsheet File'
            return HttpResponseRedirect(reverse('ingest:bican_id_upload', args=[sheet_id]) + f'?error_message={error_messages[0]}')
    else:
        # Handle GET request
        return render(request, '/')

def save_bican_ids(request):
    if request.method == 'POST':
        sheet_id, csrf_token, data_items = extract_post_data(request)
        
        specimen_id_list = []
        specimen_list = []
        nhash_info_list = []
        error_messages = []

        for spec_id, bican_id in data_items:
            spec_bil_id, local_name = process_specimen_id(spec_id)
            specimen_id_list.append(spec_bil_id)
            specimen_list.append(local_name)
            nhash_info, error_message = retrieve_nhash_info(bican_id)
            if error_message:
                error_messages.append(error_message)
                continue  # Proceed with the next iteration if there's an error
            nhash_info_list.append(nhash_info)

        if error_messages:
            # If there are any errors, handle them. This could be redirecting or displaying the error.
            # This example uses the first error message for simplicity.
            return HttpResponseRedirect(reverse('ingest:bican_id_upload', args=[sheet_id]) + f'?error_message={error_messages[0]}')
        #print("Nhash Info: ", nhash_info)
        extracted_ids = []
        for nhash_info in nhash_info_list:
            ids = extract_ids(nhash_info)  # Extract IDs for each nhash_info individually
            extracted_ids.append(ids)
        processed_ids = specimen_list_mapping(extracted_ids, specimen_id_list)  # Assuming this function exists
        processed_ids_json = json.dumps(processed_ids)
        nhash_info_list = [whitelist_filter(x) for x in nhash_info_list]
        nhash_specimen_list = zip(nhash_info_list, specimen_list)
        print("TOP KEYS:", nhash_info_list[0].keys())
        print("DATA KEYS:", list(nhash_info_list[0].get("data", {}).keys()))
        print("FIRST RECORD KEYS:", list(next(iter(nhash_info_list[0].get("data", {}).values()), {}).keys()))

        
        return render(request, 'ingest/nhash_id_confirm.html', {'nhash_specimen_list': nhash_specimen_list, 'processed_ids_json': processed_ids_json})
    else:
        # Handle GET request, maybe render the form again or redirect
        return render(request, '/')

    
def extract_post_data(request):
    sheet_id = request.POST.get('sheet_id')
    csrf_token = get_token(request)
    data_items = [(key, value) for key, value in request.POST.items() if key not in ['csrfmiddlewaretoken', 'sheet_id']]
    return sheet_id, csrf_token, data_items

def process_specimen_id(spec_id):
    spec_bil = BIL_Specimen_ID.objects.get(specimen_id=spec_id)
    spec_local = Specimen.objects.get(id=spec_id)
    return spec_bil.id, spec_local.localid

def retrieve_nhash_info(bican_id):
    nhash_info = Specimen_Portal.get_nhash_results(bican_id)
    if nhash_info == {'error': 'No data found'}:
        return None, f"We couldn't find any information for the BICAN ID: {bican_id}. Please make sure you've entered the correct BICAN ID and try again."
    return nhash_info, None

def extract_ids(nhash_info):
    ids = []
    # Check if the input is a dictionary
    if isinstance(nhash_info, dict):
        for key, value in nhash_info.items():
            if key == "data":
                # Extract keys (IDs) under 'data'
                ids.extend(value.keys())
            elif key == "has_parent" and isinstance(value, list):
                # Extract parent IDs
                ids.extend(value)
            elif isinstance(value, (dict, list)):
                # Recursively search in nested structures
                ids.extend(extract_ids(value))
    elif isinstance(nhash_info, list):
        for item in nhash_info:
            ids.extend(extract_ids(item))
    return ids
    
def specimen_list_mapping(ids_list, specimen_list):
    specimen_ids_mapping = {}
    for specimen, ids in zip(specimen_list, ids_list):
        specimen_ids_mapping[specimen] = ids
    return specimen_ids_mapping

def process_ids(request):
    if request.method == 'POST':
        # Process the received processed_ids list
        processed_ids = request.POST.get('processed_ids_json')
        processed_ids = json.loads(processed_ids)
        for specimen, nhash_ids in processed_ids.items():
            bil_specimen_id = BIL_Specimen_ID.objects.get(id = specimen)
            for id in nhash_ids:
                if id.startswith('TI'):
                    linkage = SpecimenLinkage(specimen_id = bil_specimen_id, specimen_id_2 = id, code_id = 'cubie_tissue', specimen_category = 'tissue')
                elif id.startswith('RI'):
                    linkage = SpecimenLinkage(specimen_id = bil_specimen_id, specimen_id_2 = id, code_id = 'cubie_tissue', specimen_category = 'roi')
                elif id.startswith('SL'):
                    linkage = SpecimenLinkage(specimen_id = bil_specimen_id, specimen_id_2 = id, code_id = 'cubie_tissue', specimen_category = 'slab')
                elif id.startswith('DO'):
                    linkage = SpecimenLinkage(specimen_id = bil_specimen_id, specimen_id_2 = id, code_id = 'cubie_tissue', specimen_category = 'donor')
                elif id.startswith('SC'):
                    linkage = SpecimenLinkage(specimen_id = bil_specimen_id, specimen_id_2 = id, code_id = 'cubie_tissue', specimen_category = 'section')
                linkage.save()
        # Redirect to a different view or do other processing
        return redirect('ingest:collection_list')  # Redirect to success page
    else:
        # Handle GET request, maybe render an error page
        print('failed')
        return redirect('ingest:collection_list')  # Redirect to error page

def save_nhash_specimen_list(request):
    if request.method == 'POST':
        # Retrieve the nhash_specimen_list from the POST data
        nhash_specimen_list = request.POST.get('nhash_specimen_list', '')

        # Unzip the zipped object to access its elements
        #nhash_info_list, specimen_list = zip(*nhash_specimen_list)
        
        # Process and save the nhash_specimen_list as needed
        for item in nhash_specimen_list:
            # Perform saving operation for each item
            pass  # Placeholder for actual saving logic

        # Return a JSON response indicating success
        return JsonResponse({'message': 'Data saved successfully'})
    else:
        # Return an error response if accessed via GET request
        return JsonResponse({'error': 'POST method required'})

def nhash_id_confirm(request):
    # Retrieve the nhash_info_list from the query parameters
    nhash_info_list_str = request.GET.get('nhash_info_list', '')
    
    # Split the nhash_info_list string by comma to get individual nhash_info JSON strings
    nhash_info_list = nhash_info_list_str.split(',')
    
    # Convert each nhash_info JSON string back to a dictionary
    nhash_info_list = [json.loads(info) for info in nhash_info_list]
    
    # Pass the nhash_info_list to the template for rendering
    return render(request, 'ingest/nhash_id_confirm.html', {'nhash_info_list': nhash_info_list})

def upload_descriptive_spreadsheet(filename, associated_submission, request):
    """ Helper used by image_metadata_upload and collection_detail."""
    workbook=xlrd.open_workbook(filename)
    worksheet = workbook.sheet_by_index(0)
    error = False
    try:
        missing = False
        badgrantnum = False
        has_escapes = False
        missing_fields = []
        missing_cells = []
        badchar = "\\"
        bad_str = []
        not_missing = []
        grantpattern = '[A-Z0-9\-][A-Z0-9\-][A-Z0-9A]{3}\-[A-Z0-9]{8}\-[A-Z0-9]{2}'
        for rowidx in range(worksheet.nrows):
            row = worksheet.row(rowidx)
            for colidx, cell in enumerate(row):
                if rowidx == 0:
                    if cell.value not in required_metadata:
                        missing = True
                        missingcol = colidx+1
                        missingrow = rowidx+1
                    else:
                        not_missing.append(cell.value)
                if cell.value == '':
                        missing = True
                        missingcol = colidx+1
                        missingrow = rowidx+1
                        missing_cells.append([missingrow, missingcol])
                else:
                    not_missing.append(cell.value)

        diff = lambda l1, l2: [x for x in l1 if x not in l2]
        missing_fields.append(str(diff(required_metadata, not_missing)))
        
        records = pe.iget_records(file_name=filename)
        if missing:
            error = True
            if missing_fields[0] == '[]':
                for badcells in missing_cells:
                    error_msg = 'Missing Required Information or Extra Field found in spreadsheet in row,column "{}"'.format(badcells)
                    messages.error(request, error_msg)
            else:
                missing_str = ", ".join(missing_fields)
                error_msg = 'Data missing from row "{}" column "{}". Missing required field(s) in spreadsheet: "{}". Be sure all headers in the metadata spreadsheet provided are included and correctly spelled in your spreadsheet. If issue persists please contact us at bil-support@psc.edu.'.format(missingrow, missingcol, missing_str)
                messages.error(request, error_msg)
        if has_escapes:
            error = True
            bad_str = ", ".join(bad_str)
            error_msg = 'Data contains an illegal character in string "{}"  row: "{}" column: "{}" Be sure there are no escape characters such as "\" or "^" in your spreadsheet. If issue persists please contact us at bil-support@psc.edu.'.format(illegalchar, errorrow, errorcol)
            messages.error(request, error_msg)
        if badgrantnum:
            error = True
            error_msg = 'Grant number does not match correct format for NIH grant number, "{}" in Row: {} Column: {}  must match the format "A-B1C-2D3E4F5G-6H"'.format(grantnum, grantrow, grantcol)
            messages.error(request, error_msg)
        if error:
            return error
        records = pe.iget_records(file_name=filename)
        for idx, record in enumerate(records):
            im = DescriptiveMetadata(
                collection=associated_submission,
                user=request.user)
            for k in record:
                setattr(im, k, record[k])
            im.save()
        messages.success(request, 'Descriptive Metadata successfully uploaded')
        # return redirect('ingest:image_metadata_list')
        return error
    except pe.exceptions.FileTypeNotSupported:
        error = True
        messages.error(request, "File type not supported")
        return error

# This gets called in the descriptive_metadata_upload function but we've commented that out to use upload_all_metadata_sheets instead, but prob will harvest some code from here. don't remove yet.
def upload_spreadsheet(spreadsheet_file, associated_submission, request):
    """ Helper used by metadata_upload and collection_detail."""
    fs = FileSystemStorage()
    filename = fs.save(spreadsheet_file.name, spreadsheet_file)
    error = False
    try:
        records = pe.iget_records(file_name=filename)
        # This is kinda inefficient, but we'll pre-scan the entire spreadsheet
        # before saving entries, so we don't get half-way uploaded
        # spreadsheets.
        for idx, record in enumerate(records):
            # XXX: right now, we're just checking for required fields that are
            # missing, but we can add whatever checks we want here.
            # XXX: blank rows in the spreadsheet that have some hidden
            # formatting can screw up this test
            missing = [k for k in record if k in required_metadata and not record[k]]
            if missing:
                error = True
                missing_str = ", ".join(missing)
                error_msg = 'Data missing from row {} in field(s): "{}"'.format(idx+2, missing_str)
                messages.error(request, error_msg)
        if error:
            # We have to add 2 to idx because spreadsheet rows are 1-indexed
            # and first row is header
            return error
        records = pe.iget_records(file_name=filename)
        for idx, record in enumerate(records):
            # "age" isn't required, so we need to explicitly set blank
            # entries to None or else django will get confused.
            if record['age'] == '':
                record['age'] = None
            im = ImageMetadata(
                collection=associated_submission,
                user=request.user)
            for k in record:
                setattr(im, k, record[k])
            im.save()
        messages.success(request, 'Metadata successfully uploaded')
        # return redirect('ingest:image_metadata_list')
        return error
    except pe.exceptions.FileTypeNotSupported:
        error = True
        messages.error(request, "File type not supported")
        return error
