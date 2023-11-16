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

def save_sheet_row(ingest_method, filename, collection):
    try:
        sheet = Sheet(filename=filename, date_uploaded=datetime.now(), collection_id=collection.id, ingest_method = ingest_method)
        sheet.save()
    except Exception as e:
        print(e)
    return sheet


def save_all_generic_sheets(contributors, funders, publications, sheet):
    try:
        saved_contribs = save_contributors_sheet(contributors, sheet)
        if saved_contribs:
            saved_funders = save_funders_sheet(funders, sheet)
            if saved_funders:
                saved_pubs = save_publication_sheet(publications, sheet)
                if saved_pubs:
                    return True
                else:
                    False
            else:
                False
        else:
            False
    except Exception as e:
        print(repr(e))
        return False
    
def save_all_sheets_method_1(instruments, specimen_set, images, datasets, sheet, contributors, funders, publications):
    # 1 dataset : 1 specimen : 1 image
    # only 1 single instrument row
    try:
        saved_datasets = save_dataset_sheet_method_1_or_3(datasets, sheet)
        if saved_datasets:
            saved_instruments = save_instrument_sheet_method_1(instruments, sheet)
            if saved_instruments:
                saved_specimens = save_specimen_sheet_method_1(specimen_set, sheet, saved_datasets)
                if saved_specimens:
                    saved_images = save_images_sheet_method_1(images, sheet, saved_datasets)
                    if saved_images:
                        saved_generic = save_all_generic_sheets(contributors, funders, publications, sheet)
                        if saved_generic:
                            return True
                        else:
                            False
                    else:
                        False
                else:
                    False
            else:
                False
        else:
            False
    except Exception as e:
        print(repr(e))
        return False

def save_all_sheets_method_2(instruments, specimen_set, images, datasets, sheet, contributors, funders, publications):
    # 1 dataset row, 1 instrument row, multiple specimens(have dataset FK)
    try:
        saved_datasets = save_dataset_sheet_method_2(datasets, sheet)
        if saved_datasets:
            saved_instruments = save_instrument_sheet_method_2(instruments, sheet)
            if saved_instruments:
                saved_specimens = save_specimen_sheet_method_2(specimen_set, sheet, saved_datasets)
                if saved_specimens:
                    saved_images = save_images_sheet_method_2(images, sheet, saved_datasets)
                    if saved_images:
                        #o = open("/tmp/submiterror.txt", "a")
                        #o.write('save_images is true')
                        saved_generic = save_all_generic_sheets(contributors, funders, publications, sheet)
                        if saved_generic:
                            #o.write('saved_generic is true')
                            return True
                        else:
                            #o.write('saved_generic is FALSE')
                            False
                    else:
                        False
                else:
                    False
            else:
                False
        else:
            False
    except Exception as e:
        print(repr(e))
        return False

def save_all_sheets_method_3(instruments, specimen_set, images, datasets, sheet, contributors, funders, publications):
    # 1 dataset : 1 specimen : 1 image
    # only 1 single instrument row
    try:
        saved_datasets = save_dataset_sheet_method_1_or_3(datasets, sheet)
        if saved_datasets:
            saved_instruments = save_instrument_sheet_method_3(instruments, sheet)
            if saved_instruments:
                saved_specimens = save_specimen_sheet_method_3(specimen_set, sheet, saved_datasets)
                if saved_specimens:
                    saved_images = save_images_sheet_method_3(images, sheet, saved_datasets)
                    if saved_images:
                        saved_generic = save_all_generic_sheets(contributors, funders, publications, sheet)
                        if saved_generic:
                            return True
                        else:
                            False
                    else:
                        False
                else:
                    False
            else:
                False
        else:
            False
    except Exception as e:
        print(repr(e))
        return False

def save_all_sheets_method_4(instruments, specimen_set, images, datasets, sheet, contributors, funders, publications):
    # instrument:dataset:images are 1:1:1 
    # 1 entry in specimen tab so each dataset gets the specimen id
    try:
        specimen_object_method_4 = save_specimen_sheet_method_4(specimen_set, sheet)
        if specimen_object_method_4:
            saved_datasets = save_dataset_sheet_method_4(datasets, sheet, specimen_object_method_4)
            if saved_datasets:
                saved_instruments = save_instrument_sheet_method_4(instruments, sheet, saved_datasets)
                if saved_instruments:
                    saved_images = save_images_sheet_method_4(images, sheet, saved_datasets)
                    if saved_images:
                        saved_generic = save_all_generic_sheets(contributors, funders, publications, sheet)
                        if saved_generic:
                            return True
                        else:
                            return False
                    else:
                        False
                else:
                    False
            else:
                False
        else:
            False
    except Exception as e:
        print(repr(e))
        saved = False

def save_all_sheets_method_5(instruments, specimen_set, datasets, sheet, contributors, funders, publications, swcs):
	# if swc tab filled out we don't want images
	# 1 dataset row should be filled out
	# many SWC : 1 dataset
    # 1 specimen
    # 1 instrument
	# 1 datasest

    try:
        specimen_object_method_5 = save_specimen_sheet_method_5(specimen_set, sheet)
        if specimen_object_method_5:
            saved_datasets = save_dataset_sheet_method_5(datasets, sheet, specimen_object_method_5)
            if saved_datasets:
                saved_instruments = save_instrument_sheet_method_5(instruments, sheet, saved_datasets)
                if saved_instruments:
                  saved_swc = save_swc_sheet(swcs, sheet, saved_datasets)
                  if saved_swc:
                      saved_generic = save_all_generic_sheets(contributors, funders, publications, sheet)
                      if saved_generic:
                          return True
                      else:
                          return False
                  else:
                    False
                else:
                    False
            else:
                False
        else:
            False
    except Exception as e:
        print(repr(e))
        saved = False

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
    ingest_method = ingest_method
    errormsg = check_contributors_sheet(filename)
    if errormsg != '':
        return errormsg
    errormsg = check_funders_sheet(filename)
    if errormsg != '':
        return errormsg
    errormsg = check_publication_sheet(filename)
    if errormsg != '':
        return errormsg
    errormsg = check_instrument_sheet(filename)
    if errormsg != '':
        return errormsg
    errormsg = check_dataset_sheet(filename)
    if errormsg != '':
        return errormsg
    errormsg = check_specimen_sheet(filename)
    if errormsg != '':
        return errormsg
    if ingest_method != 'ingest_5':
        errormsg = check_image_sheet(filename)
        if errormsg != '':
            return errormsg
    if ingest_method == 'ingest_5':
        errormsg = check_swc_sheet(filename)
        if errormsg != '':
            return errormsg
    return errormsg

@login_required
def descriptive_metadata_upload(request):
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
        form = UploadForm(request.POST)

        ingest_method = request.POST.get('ingest_method', False)
	
        if form.is_valid():
            associated_collection = form.cleaned_data['associated_collection']

            # for production
            # datapath = associated_collection.data_path.replace("/lz/","/etc/")
            
            # for development on vm
            # datapath = '/home/shared_bil_dev/testetc/' 

            # for development locally
            datapath = config['Security']['DATAPATH'] 
            
            spreadsheet_file = request.FILES['spreadsheet_file']

            fs = FileSystemStorage(location=datapath)
            name_with_path = datapath + '/' + spreadsheet_file.name
            fs.save(name_with_path, spreadsheet_file)
            filename = name_with_path

            version1 = metadata_version_check(filename)
            
            # using old metadata model for any old submissions (will eventually be deprecated)
            if version1 == True:
                error = upload_descriptive_spreadsheet(filename, associated_collection, request)
                if error:
                    return redirect('ingest:descriptive_metadata_upload')
                else:         
                    return redirect('ingest:descriptive_metadata_list')
            
            # using new metadata model
            elif version1 == False:
                errormsg = check_all_sheets(filename, ingest_method)
                if errormsg != '':
                    messages.error(request, errormsg)
                    return redirect('ingest:descriptive_metadata_upload')

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

                    # choose save method depending on ingest_method value from radio button
                    # want to pull this out into a helper function
                    if ingest_method == 'ingest_1':
                        sheet = save_sheet_row(ingest_method, filename, collection)
                        saved = save_all_sheets_method_1(instruments, specimen_set, images, datasets, sheet, contributors, funders, publications)
                    elif ingest_method == 'ingest_2':
                        sheet = save_sheet_row(ingest_method, filename, collection)
                        saved = save_all_sheets_method_2(instruments, specimen_set, images, datasets, sheet, contributors, funders, publications)
                    elif ingest_method == 'ingest_3':
                        sheet = save_sheet_row(ingest_method, filename, collection)
                        saved = save_all_sheets_method_3(instruments, specimen_set, images, datasets, sheet, contributors, funders, publications)
                    elif ingest_method == 'ingest_4':
                        sheet = save_sheet_row(ingest_method, filename, collection)
                        saved = save_all_sheets_method_4(instruments, specimen_set, images, datasets, sheet, contributors, funders, publications)
                    elif ingest_method == 'ingest_5':
                        sheet = save_sheet_row(ingest_method, filename, collection)
                        saved = save_all_sheets_method_5(instruments, specimen_set, datasets, sheet, contributors, funders, publications, swcs)
                    elif ingest_method != 'ingest_1' and ingest_method != 'ingest_2' and ingest_method != 'ingest_3' and ingest_method != 'ingest_4' and ingest_method != 'ingest_5':
                         saved = False
                         messages.error(request, 'You must choose a value from "Step 2 of 3: What does your data look like?"')                         
                         return redirect('ingest:descriptive_metadata_upload')
                    if saved == True:
                         messages.success(request, 'Descriptive Metadata successfully uploaded!!')
                         return redirect('ingest:descriptive_metadata_list')
                    else:
                         error_code = sheet.id
                         messages.error(request, 'There has been an error. Please contact BIL Support. Error Code: ', error_code)
                         return redirect('ingest:descriptive_metadata_upload')


    # This is the GET (just show the metadata upload page)
    else:
        user = request.user
        form = UploadForm()
        # Only let a user associate metadata with an unlocked collection that they own
        form.fields['associated_collection'].queryset = Collection.objects.filter(
            locked=False, user=request.user)
        collections = form.fields['associated_collection'].queryset
    collections = Collection.objects.filter(locked=False, user=request.user)
    
    return render( request, 'ingest/descriptive_metadata_upload.html',{'form': form, 'pi':pi, 'collections':collections})

def upload_descriptive_spreadsheet(filename, associated_collection, request):
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
                collection=associated_collection,
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
        return error
