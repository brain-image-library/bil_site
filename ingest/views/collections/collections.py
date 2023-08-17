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

@login_required
def collection_send(request):
    content = json.loads(request.body)
    items = []
    user_name = request.user
    for item in content:
        items.append(item['bil_uuid'])
        coll = Collection.objects.get(bil_uuid = item['bil_uuid'])
        coll_id = Collection.objects.get(id = coll.id)
        person = People.objects.get(name = user_name)
        person_id = person.id
        time = datetime.now()
        event = EventsLog(collection_id = coll_id, people_id_id = person.id, project_id_id = coll.project_id, notes = '', timestamp = time, event_type = 'request_validation')
        event.save()
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
    messages.success(request, 'Request succesfully sent')
    return HttpResponse(json.dumps({'url': reverse('ingest:index')}))

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
        datasets_list = []
        collection = Collection.objects.get(id=pk)
        sheets = Sheet.objects.filter(collection_id=collection.id).last()
        #for s in sheets:
        if sheets != None:
            datasets = Dataset.objects.filter(sheet_id=sheets.id)
            for d in datasets:
                datasets_list.append(d)
    except ObjectDoesNotExist:
        raise Http404
    # the metadata associated with this collection
    #image_metadata_queryset = collection.imagemetadata_set.all()
    descriptive_metadata_queryset = collection.descriptivemetadata_set.last()
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
         'pi': pi, 'datasets_list':datasets_list})

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