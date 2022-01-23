from calendar import c
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
from openpyxl import load_workbook
import xlrd
import re
from celery.result import AsyncResult

from . import tasks
from .field_list import required_metadata
from .filters import CollectionFilter
from .forms import CollectionForm, ImageMetadataForm, DescriptiveMetadataForm, UploadForm, collection_send
from .models import UUID, Collection, ImageMetadata, DescriptiveMetadata, Project, ProjectPeople, People, Project, EventsLog, Contributor, Funder, Publication, Instrument, Dataset, Species, Image, DataState
from .tables import CollectionTable, ImageMetadataTable, DescriptiveMetadataTable, CollectionRequestTable
import uuid
import datetime
import json

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
    try:
        people = People.objects.get(auth_user_id_id = current_user.id)
        project_person = ProjectPeople.objects.filter(people_id = people.id).all()
        if people.is_bil_admin:
            return render(request, 'ingest/bil_index.html', {'people':people})
        for attribute in project_person: 
            if attribute.is_pi:
                return render(request, 'ingest/pi_index.html', {'project_person': attribute})
    except Exception as e:
        print(e)
    return render(request, 'ingest/index.html')


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
      
    return render(request, 'ingest/manage_projects.html', {'allprojects':allprojects, 'pi':pi})

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
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False
    return render(request, 'ingest/project_form.html', {'pi':pi})

# takes the data from project_form
@login_required
def create_project(request):
    new_project = json.loads(request.body)
    items = []
    for item in new_project:
        items.append(item['funded_by'])
        items.append(item['is_biccn'])
        items.append(item['name'])
        
        funded_by = item['funded_by']
        is_biccn = item['is_biccn']
        name = item['name']
        
        # write project to the project table   
        project = Project(funded_by=funded_by, is_biccn=is_biccn, name=name)
        project.save()
        
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

@login_required
def descriptive_metadata_upload(request):
    current_user = request.user
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else: 
            pi = False    
    """ Upload a spreadsheet containing image metadata information. """
    # The POST. A user has selected a file and associated collection to upload.
    if request.method == 'POST' and request.FILES['spreadsheet_file']:
        form = UploadForm(request.POST)
        if form.is_valid():
            collection = form.cleaned_data['associated_collection']
            # for production
            #datapath=collection.data_path.replace("/lz/","/etc/")
            
            # for development 
            datapath = '/home/shared_bil_dev/testetc/' 
            
            spreadsheet_file = request.FILES['spreadsheet_file']
        
            error = upload_descriptive_spreadsheet(spreadsheet_file, collection, request, datapath)
            if error:
                return redirect('ingest:descriptive_metadata_upload')
            else:         
                return redirect('ingest:descriptive_metadata_list')
    # This is the GET (just show the metadata upload page)
    else:
        user = request.user
        form = UploadForm()
        # Only let a user associate metadata with an unlocked collection that
        # they own
        form.fields['associated_collection'].queryset = Collection.objects.filter(
            locked=False, user=request.user)
        collections = form.fields['associated_collection'].queryset
    collections = Collection.objects.filter(locked=False, user=request.user)
    
    return render( request, 'ingest/descriptive_metadata_upload.html',{'form': form, 'pi':pi, 'collections':collections})

# do we still use this???
@login_required
def image_metadata_upload(request):
    """ Upload a spreadsheet containing image metadata information. """

    # The POST. Auser has selected a file and associated collection to upload.
    if request.method == 'POST' and request.FILES['spreadsheet_file']:
        form = UploadForm(request.POST)
        if form.is_valid():
            collection = form.cleaned_data['associated_collection']
            spreadsheet_file = request.FILES['spreadsheet_file']
            error = upload_spreadsheet(spreadsheet_file, collection, project, request)
            if error:
                return redirect('ingest:image_metadata_upload')
            else:
                return redirect('ingest:image_metadata_list')
    # This is the GET (just show the metadata upload page)
    else:
        form = UploadForm()
        # Only let a user associate metadata with an unlocked collection that
        # they own
        form.fields['associated_collection'].queryset = Collection.objects.filter(
            locked=False, user=request.user)
    collections = Collection.objects.filter(locked=False, user=request.user)
    return render(
        request,
        'ingest/image_metadata_upload.html',
        {'form': form, 'collections': collections})



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
        print(key)     
        messages.success(request, request.POST[key])
        print (request.POST[key])      
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
        descriptive_metadata = DescriptiveMetadata.objects.filter(user=request.user)
        return render(
            request,
            'ingest/descriptive_metadata_list.html',
            {'table': table, 'descriptive_metadata': descriptive_metadata, 'pi':pi})



@login_required
def image_metadata_list(request):
    """ A list of all the metadata the user has created. """
    # The user is trying to delete the selected metadata
    if request.method == "POST":
        pks = request.POST.getlist("selection")
        # Get all of the checked metadata (except LOCKED metadata)
        selected_objects = ImageMetadata.objects.filter(
            pk__in=pks, locked=False)
        selected_objects.delete()
        messages.success(request, 'Metadata successfully deleted')
        return redirect('ingest:image_metadata_list')
    # This is the GET (just show the user their list of metadata)
    else:
        # XXX: This exclude is likely redundant, becaue there's already the
        # same exclude in the class itself. Need to test though.
        table = ImageMetadataTable(
            ImageMetadata.objects.filter(user=request.user), exclude=['user','bil_uuid'])
        RequestConfig(request).configure(table)
        image_metadata = ImageMetadata.objects.filter(user=request.user)
        return render(
            request,
            'ingest/image_metadata_list.html',
            {'table': table, 'image_metadata': image_metadata})


class ImageMetadataDetail(LoginRequiredMixin, DetailView):
    """ A detailed view of a single piece of metadata. """
    model = ImageMetadata
    template_name = 'ingest/image_metadata_detail.html'
    context_object_name = 'image_metadata'


class DescriptiveMetadataDetail(LoginRequiredMixin, DetailView):
    """ A detailed view of a single piece of metadata. """
    model = DescriptiveMetadata
    template_name = 'ingest/descriptive_metadata_detail.html'
    context_object_name = 'descriptive_metadata'


@login_required
def image_metadata_create(request):
    """ Create new image metadata. """
    # The user has hit the "Save" button on the "Create Metadata" page.
    if request.method == "POST":
        # We need to pass in request here, so we can use it to get the user
        form = ImageMetadataForm(request.POST, user=request.user)
        if form.is_valid():
            post = form.save(commit=False)
            post.save()
            messages.success(request, 'Metadata successfully created')
            return redirect('ingest:image_metadata_list')
    # The GET. Just show the user the blank "Create Metadata" form.
    else:
        form = ImageMetadataForm(user=request.user)
        # Only let a user associate metadata with an unlocked collection that
        # they own
        form.fields['collection'].queryset = Collection.objects.filter(
            locked=False, user=request.user)
    return render(request, 'ingest/image_metadata_create.html', {'form': form})


class ImageMetadataUpdate(LoginRequiredMixin, UpdateView):
    """ Modify an existing piece of image metadata. """
    model = ImageMetadata
    template_name = 'ingest/image_metadata_update.html'
    success_url = reverse_lazy('ingest:image_metadata_list')
    form_class = ImageMetadataForm

    def get_form_kwargs(self):
        kwargs = super(ImageMetadataUpdate, self).get_form_kwargs()
        kwargs.update({'user': self.request.user})
        return kwargs


class ImageMetadataDelete(LoginRequiredMixin, DeleteView):
    """ Delete an existing piece of image metadata. """
    model = ImageMetadata
    template_name = 'ingest/image_metadata_delete.html'
    success_url = reverse_lazy('ingest:image_metadata_list')

# What follows is a number of views for uploading, creating, viewing, modifying
# and deleting COLLECTIONS.


@login_required
def collection_send(request):
    content = json.loads(request.body)
    print(content)
    items = []
    user_name = request.user
    for item in content:
        items.append(item['bil_uuid'])
        
    if request.method == "POST":
        subject = '[BIL Validations] New Validation Request'
        sender = 'ltuite96@psc.edu'
        message = F'The following collections have been requested to be validated {items} by {user_name}@psc.edu'
        recipient = ['ltuite96@psc.edu']
        
        send_mail(
        subject,
        message,
        sender,
        recipient
             )
        print(message)
        print(user_name)
    messages.success(request, 'Request succesfully sent')
    return HttpResponse(json.dumps({'url': reverse('ingest:index')}))

@login_required
def collection_create(request):
    current_user = request.user
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id).all()
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
        top_level_dir = settings.STAGING_AREA_ROOT
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
        print(form)
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
            cache.delete('host_and_path')
            cache.delete('data_path')
            cache.delete('bil_uuid')
            cache.delete('bil_user')
            messages.success(request, 'Collection successfully created!! Please proceed with data upload and metadata upload')
            return redirect('ingest:descriptive_metadata_upload')
    else:
        form = CollectionForm()

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
    """ A list of all a user's collections. """

    table_class = CollectionRequestTable
    model = Collection
    template_name = 'ingest/submit_request_collection_list.html'
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
    success_url = reverse_lazy('ingest:collection_list')

class CollectionList(LoginRequiredMixin, SingleTableMixin, FilterView):
    """ A list of all a user's collections. """

    table_class = CollectionTable
    model = Collection
    template_name = 'ingest/collection_list.html'
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
def collection_validation_results(request, pk):
    current_user = request.user
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False
    """ Where a user can see the results of validation. """
    collection = Collection.objects.get(id=pk)

    collection.validation_status = "NOT_VALIDATED"
    dir_size = ""
    outvalidfile = ""
    filecontents = ""
    invalid_metadata_directories = []
    if collection.celery_task_id_validation:
        result = AsyncResult(collection.celery_task_id_validation)
        state = result.state
        if state == 'SUCCESS':
            analysis_results = result.get()
            if analysis_results['valid']:
                collection.validation_status = "SUCCESS"
            else:
                collection.validation_status = "FAILED"
                invalid_metadata_directories = analysis_results["invalid_metadata_directories"]
            dir_size = analysis_results['dir_size']
            outvalidfile = analysis_results['output']
            #Open the log file and read the contents
            f=open(outvalidfile, "r")
            if f.mode == 'r':
               filecontents=f.read()
            f.close()
        else:
            collection.validation_status = "PENDING"

    return render(
        request,
        'ingest/collection_validation_results.html',
        {'collection': collection,
         'outfile': outvalidfile,
         'output': filecontents,
         'dir_size': dir_size,
         'invalid_metadata_directories': invalid_metadata_directories,
         'pi': pi})


@login_required
def collection_submission_results(request, pk):
    current_user = request.user
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False
    """ Where a user can see the results of submission. """
    collection = Collection.objects.get(id=pk)

    collection.submission_status = "NOT_SUBMITTED"
    dir_size = ""
    outvalidfile = ""
    filecontents = ""
    invalid_metadata_directories = []
    if collection.celery_task_id_submission:
        result = AsyncResult(collection.celery_task_id_submission)
        state = result.state
        if state == 'SUCCESS':
            analysis_results = result.get()
            if analysis_results['valid']:
                collection.submission_status = "SUCCESS"
            else:
                collection.submission_status = "FAILED"
                invalid_metadata_directories = analysis_results["invalid_metadata_directories"]
            dir_size = analysis_results['dir_size']
            outvalidfile = analysis_results['output']
            #Open the log file and read the contents
            f=open(outvalidfile, "r")
            if f.mode == 'r':
               filecontents=f.read()
            f.close()
        else:
            collection.submission_status = "PENDING"

    return render(
        request,
        'ingest/collection_submission_results.html',
        {'collection': collection,
         'outfile': outvalidfile,
         'output': filecontents,
         'dir_size': dir_size,
         'invalid_metadata_directories': invalid_metadata_directories,
         'pi': pi})


@login_required
def collection_detail(request, pk):
    current_user = request.user
    people = People.objects.get(auth_user_id_id = current_user.id)
    project_person = ProjectPeople.objects.filter(people_id = people.id).all()
    for attribute in project_person:
        if attribute.is_pi:
            pi = True
        else:
            pi = False
    """ View, edit, delete, create a particular collection. """
    # If user tries to go to a page using a collection primary key that doesn't
    # exist, give a 404
    try:
        collection = Collection.objects.get(id=pk)
    except ObjectDoesNotExist:
        raise Http404
    # the metadata associated with this collection
    #image_metadata_queryset = collection.imagemetadata_set.all()
    descriptive_metadata_queryset = collection.descriptivemetadata_set.all()
    # this is what is triggered if the user hits "Upload to this Collection"
    if request.method == 'POST' and 'spreadsheet_file' in request.FILES:
        spreadsheet_file = request.FILES['spreadsheet_file']
        upload_spreadsheet(spreadsheet_file, collection, request)
        return redirect('ingest:collection_detail', pk=pk)
    # this is what is triggered if the user hits "Submit collection"
    elif request.method == 'POST' and 'validate_collection' in request.POST:
        #---trying to model validate_collection this after submit_collection
        # lock everything (collection and associated image metadata) during
        # submission and validation. if successful, keep it locked
        collection.locked = False
        metadata_dirs = []
        for im in descriptive_metadata_queryset:
        #for im in image_metadata_queryset:
            im.locked = True
            im.save()
            metadata_dirs.append(im.r24_directory)
            #metadata_dirs.append(im.directory)
        # This is just a very simple test, which will be replaced with some
        # real validation and analysis in the future
        if not settings.FAKE_STORAGE_AREA:
            data_path = collection.data_path.__str__()
            task = tasks.run_validate.delay(data_path, metadata_dirs)
            collection.celery_task_id_validation = task.task_id
        collection.save()
        return redirect('ingest:collection_detail', pk=pk)
    elif request.method == 'POST' and 'submit_collection' in request.POST:
        # lock everything (collection and associated image metadata) during
        # submission and validation. if successful, keep it locked
        collection.locked = True
        metadata_dirs = []
        for im in descriptive_metadata_queryset:
        #for im in image_metadata_queryset:
            im.locked = True
            im.save()
            metadata_dirs.append(im.r24_directory)
        #    metadata_dirs.append(im.directory)
        # This is just a very simple test, which will be replaced with some
        # real validation and analysis in the future
        if not settings.FAKE_STORAGE_AREA:
            data_path = collection.data_path.__str__()
            task = tasks.run_analysis.delay(data_path, metadata_dirs)
            collection.celery_task_id_submission = task.task_id
        collection.save()
        return redirect('ingest:collection_detail', pk=pk)

    # check submission status
    if collection.celery_task_id_submission:
        result = AsyncResult(collection.celery_task_id_submission)
        state = result.state
        if state == 'SUCCESS':
            analysis_results = result.get()
            if analysis_results['valid']:
                collection.submission_status = "SUCCESS"
            else:
                collection.submission_status = "FAILED"
                # need to unlock, so user can fix problem
                collection.locked = False
                #for im in image_metadata_queryset:
                for im in descriptive_metadata_queryset:
                    im.locked = False
                    im.save()
        else:
            collection.submission_status = "PENDING"
    collection.save()

   # check validation status
    if collection.celery_task_id_validation:
        result = AsyncResult(collection.celery_task_id_validation)
        state = result.state
        if state == 'SUCCESS':
            analysis_results = result.get()
            if analysis_results['valid']:
                collection.validation_status = "SUCCESS"
            else:
                collection.validation_status = "FAILED"
                # need to unlock, so user can fix problem
                collection.locked = False
                #for im in image_metadata_queryset:
                for im in descriptive_metadata_queryset:
                    im.locked = False
                    im.save()
        else:
            collection.validation_status = "PENDING"
    collection.save()
    table = DescriptiveMetadataTable(
        DescriptiveMetadata.objects.filter(user=request.user, collection=collection))
    return render(
        request,
        'ingest/collection_detail.html',
        {'table': table,
         'collection': collection,
         'descriptive_metadata_queryset': descriptive_metadata_queryset,
         'pi': pi})

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


def upload_spreadsheet(spreadsheet_file, associated_collection, request):
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
            # return redirect('ingest:image_metadata_upload')
            return error
        records = pe.iget_records(file_name=filename)
        for idx, record in enumerate(records):
            # "age" isn't required, so we need to explicitly set blank
            # entries to None or else django will get confused.
            if record['age'] == '':
                record['age'] = None
            im = ImageMetadata(
                collection=associated_collection,
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
        # return redirect('ingest:image_metadata_upload')
        return error

def check_contributors_sheet(spreadsheet_file, request, datapath):
    name_with_path=datapath + '/' + spreadsheet_file.name
    filename = fs.save(name_with_path, spreadsheet_file)
    fn = load_workbook(filename)
    contributors = fn.get_sheet_by_name('Contributors')
    
    missing = False

    for row in contributors.iter_rows(min_row=4, max_col=8):
        for cell in row:
            print('%s: cell.value=%s' % (cell, cell.value) )
            if cell.value not in contributor_metadata:
                missing = True
            if cell.value == '':
                missing = True
    if missing:
                error = True
                missing_str = ", ".join(missing)
                error_msg = 'Data missing from row {} in field(s): "{}"'.format(idx+2, missing_str)
                messages.error(request, error_msg)
    
def ingest_contributors_sheet(spreadsheet_file, datapath):
    fs = FileSystemStorage(location=datapath)
    name_with_path=datapath + '/' + spreadsheet_file.name
    filename = fs.save(name_with_path, spreadsheet_file)
    fn = load_workbook(filename)
    contributors_sheet = fn.get_sheet_by_name('Contributors')

    header = ['contributorName',
        'creator',
        'contributorType',
        'nameType',
        'nameIdentifier'
        'nameIdentifierScheme',
        'affiliation',
        'affiliationIdentifier',
        'affiliationIdentifierScheme']
       
    contributors = []
    
    for row in contributors_sheet.rows[4:]:
        values = {}
        for key, cell in zip(header, row):
            values[key] = cell.value
            contributor = Contributor(**values)
            contributors.append(contributor)

    return contributors

def ingest_funders_sheet(spreadsheet_file, datapath):
    fs = FileSystemStorage(location=datapath)
    name_with_path=datapath + '/' + spreadsheet_file.name
    filename = fs.save(name_with_path, spreadsheet_file)
    fn = load_workbook(filename)
    funders_sheet = fn.get_sheet_by_name('Funders')

    header = ['name',
        'funding_reference_identifier',
        'funding_reference_identifier_type',
        'award_number',
        'award_title']
       
    funders = []
    
    for row in funders_sheet.rows[4:]:
        values = {}
        for key, cell in zip(header, row):
            values[key] = cell.value
            funder = Funder(**values)
            funders.append(funder)

    return funders

def ingest_publication_sheet(spreadsheet_file, datapath):
    fs = FileSystemStorage(location=datapath)
    name_with_path=datapath + '/' + spreadsheet_file.name
    filename = fs.save(name_with_path, spreadsheet_file)
    fn = load_workbook(filename)
    publication_sheet = fn.get_sheet_by_name('Publication')

    header = ['relatedIdentifier',
        'relatedIdentifierType',
        'pmcid',
        'relationType',
        'citation']
       
    publications = []
    
    for row in publication_sheet.rows[4:]:
        values = {}
        for key, cell in zip(header, row):
            values[key] = cell.value
            publication = Publication(**values)
            publications.append(publication)

    return publications

def ingest_instrument_sheet(spreadsheet_file, datapath):
    fs = FileSystemStorage(location=datapath)
    name_with_path=datapath + '/' + spreadsheet_file.name
    filename = fs.save(name_with_path, spreadsheet_file)
    fn = load_workbook(filename)
    instrument_sheet = fn.get_sheet_by_name('Instrument')

    header = ['microscopeType',
        'microscopeManufacturerAndModel',
        'objectiveName',
        'objectiveImmersion',
        'objectiveNA',
        'objectiveMagnification',
        'detectorType',
        'detectorModel',
        'illuminationTypes',
        'illuminationWavelength',
        'detectionWavelength',
        'sampleTemperature']
       
    instruments = []
    
    for row in instrument_sheet.rows[4:]:
        values = {}
        for key, cell in zip(header, row):
            values[key] = cell.value
            instrument = Instrument(**values)
            instruments.append(instrument)

    return instruments

def ingest_dataset_sheet(spreadsheet_file, datapath):
    fs = FileSystemStorage(location=datapath)
    name_with_path=datapath + '/' + spreadsheet_file.name
    filename = fs.save(name_with_path, spreadsheet_file)
    fn = load_workbook(filename)
    dataset_sheet = fn.get_sheet_by_name('Dataset')

    header = ['bilDirectory',
        'title',
        'socialMedia',
        'subject',
        'subjectScheme',
        'rights',
        'rightsURI',
        'rightsIdentifier',
        'image',
        'generalModality',
        'technique',
        'other',
        'abstract',
        'methods',
        'technicalInfo']
       
    datasets = []
    
    for row in dataset_sheet.rows[4:]:
        values = {}
        for key, cell in zip(header, row):
            values[key] = cell.value
            dataset = Dataset(**values)
            datasets.append(dataset)

    return datasets

def ingest_species_sheet(spreadsheet_file, datapath):
    fs = FileSystemStorage(location=datapath)
    name_with_path=datapath + '/' + spreadsheet_file.name
    filename = fs.save(name_with_path, spreadsheet_file)
    fn = load_workbook(filename)
    species_sheet = fn.get_sheet_by_name('Species')

    header = ['localID',
        'species',
        'ncbiTaxonomy',
        'age',
        'ageUnit',
        'sex',
        'genotype',
        'organLocalID',
        'organName',
        'sampleLocalID',
        'atlas',
        'locations']
       
    species = []
    
    for row in species_sheet.rows[4:]:
        values = {}
        for key, cell in zip(header, row):
            values[key] = cell.value
            specie_row = Species(**values)
            species.append(specie_row)

    return species

def ingest_image_sheet(spreadsheet_file, datapath):
    fs = FileSystemStorage(location=datapath)
    name_with_path=datapath + '/' + spreadsheet_file.name
    filename = fs.save(name_with_path, spreadsheet_file)
    fn = load_workbook(filename)
    image_sheet = fn.get_sheet_by_name('Image')

    header = ['xAxis',
        'obliqueXdim1',
        'obliqueXdim2',
        'obliqueXdim3',
        'yAxis',
        'obliqueYdim1',
        'obliqueYdim2',
        'obliqueYdim3',
        'zAxis',
        'obliqueZdim1',
        'obliqueZdim2',
        'obliqueZdim3',
        'landmarkName',
        'landmarkX',
        'landmarkY',
        'Number',
        'displayColor',
        'Representation',
        'Flurophore',
        'stepSizeX',
        'stepSizeY',
        'stepSizeZ',
        'stepSizeT',
        'Channels',
        'Slices',
        'z',
        'Xsize',
        'Ysize',
        'Zsize',
        'Gbytes',
        'Files',
        'DimensionOrder']
       
    images = []
    
    for row in image_sheet.rows[4:]:
        values = {}
        for key, cell in zip(header, row):
            values[key] = cell.value
            image = Image(**values)
            images.append(image)

    return images

def ingest_datastate_sheet(spreadsheet_file, datapath):
    fs = FileSystemStorage(location=datapath)
    name_with_path=datapath + '/' + spreadsheet_file.name
    filename = fs.save(name_with_path, spreadsheet_file)
    fn = load_workbook(filename)
    datastate_sheet = fn.get_sheet_by_name('DataState')

    header = ['level',
        'included',
        'location',
        'attributes',
        'description']
       
    datastates = []
    
    for row in datastate_sheet.rows[4:]:
        values = {}
        for key, cell in zip(header, row):
            values[key] = cell.value
            datastate = DataState(**values)
            datastates.append(datastate)

    return datastates

def check_all_sheets()
    good = True
    check_contributors_sheet()
    check_funders_sheet()
    check_publication_sheet()
    check_instrument_sheet()
    check_dataset_sheet()
    check_specimen_sheet()
    check_image_sheet()
    check_datastate_sheet()
    return good

def save_all_sheets()
    save_contributors_sheet()
    save_funders_sheet()
    save_publication_sheet()
    save_instrument_sheet()
    save_dataset_sheet()
    save_specimen_sheet()
    save_image_sheet()
    save_datastate_sheet()
    return

def ingest_all_metadata_sheets(good)
    check_all_sheets(good)
    if good:
        try:
            ingest_all_sheets()
            if good:
                try:
                    save_all_sheets()
                # for every contributor in contributors
                # add the sheet_id to the row
                # save row to contributors table

    return

        
    
    







def upload_descriptive_spreadsheet(spreadsheet_file, associated_collection, request, datapath):
    """ Helper used by metadata_upload and collection_detail."""
    fs = FileSystemStorage(location=datapath)
    name_with_path=datapath + '/' + spreadsheet_file.name 
    filename = fs.save(name_with_path, spreadsheet_file)
    fn = load_workbook(filename)
    row_count = sheet.max_row
    column_count = sheet.nax_column
     
    contributors = fn.get_sheet_by_name('Contributors')
    funders = fn.get_sheet_by_name('Funders')
    publication = fn.get_sheet_by_name('Publication')
    instrument = fn.get_sheet_by_name('Instrument')
    dataset = fn.get_sheet_by_name('Dataset')
    specimen = fn.get_sheet_by_name('Specimen')
    image = fn.get_sheet_by_name('Image')
    datastate = fn.get_sheet_by_name('DataState')
    
    error = False
    missing = False
    badgrantnum = False
    has_escapes = False
    missing_fields = []
    missing_cells = []
    badchar = "\\"
    bad_str = []
    contributors_cells = []
    contributors_rows = [] 
    funders_cells = []
    funders_rows = []
    publication_cells = []
    publication_rows = []
    instrument_cells = []
    instrument_rows = []
    dataset_cells = []
    dataset_rows = []
    specimen_cells = []
    speciment_rows = []
    image_cells = []
    image_rows = []
    datastate_cells = []
    datastate_rows = []
    grantpattern = '[A-Z0-9\-][A-Z0-9\-][A-Z0-9A]{3}\-[A-Z0-9]{8}\-[A-Z0-9]{2}'
    
    if missing == True:
        return print('Some of the data in your spreadsheet is missing')
    else:
        Try:
            sheet = Sheet(filename=filename)
            # for every row in a tab, assign to the corresponding object, then save to db
            # for c in contributor_rows:
                # contributor = Contributor(  
                # contributor.save()
            # funders.save()
            # publication.save()
            # instrument.save()
            # dataset.save()
            # specimen.save()
            # image.save()
            # image.save()
            # datastate.save()
            # sheet.save()







    return print('All done!')


