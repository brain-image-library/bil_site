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

def check_swc_sheet(filename):
    swc_count = 0
    errormsg=""
    workbook=xlrd.open_workbook(filename)
    sheetname = 'SWC'
    swc_sheet = workbook.sheet_by_name(sheetname)
    colheads=['tracingFile', 'sourceData', 'sourceDataSample', 'sourceDataSubmission', 'coordinates', 'coordinatesRegistration', 'brainRegion', 'brainRegionAtlas', 'brainRegionAtlasName', 'brainRegionAxonalProjection', 'brainRegionDendriticProjection', 'neuronType', 'segmentTags', 'proofreadingLevel', 'Notes']
    cellcols=['A','B','C','D','E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O']
    coordinatesRegistration = ['Yes', 'No']
    cols=swc_sheet.row_values(3)
    for i in range(0,len(colheads)):
        if cols[i] != colheads[i]:
            errormsg = errormsg + ' Tab: "SWC" cell heading found: "' + cols[i] + \
                       '" but expected: "' + colheads[i] + '" at cell: "' + cellcols[i] + '3". '
    if errormsg != "":
        return [ True, errormsg ]
    for i in range(6,swc_sheet.nrows):
        swc_count = swc_count + 1
        cols=swc_sheet.row_values(i)
        #if xAxis is oblique, oblique cols should reflect 
        if cols[0] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname + 'Column: "' + colheads[0] + '" value expected but not found in cell: "' + cellcols[0] + str(i+1) + '". '
        if cols[5] == "":
           errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[5] + '" value expected but not found in cell "' + cellcols[5] + str(i+1) + '". '
        if cols[5] != "":
            if cols[5] not in coordinatesRegistration:
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[5] + '" incorrect CV value found: "' + cols[5] + '" in cell "' + cellcols[5] + str(i+1) + '". '
            if cols[5] == 'Yes':
              if cols[6] == "":
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[6] + '" value expected but not found in cell "' + cellcols[6] + str(i+1) + '". '
              if cols[7] == "":
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[7] + '" value expected but not found in cell "' + cellcols[7] + str(i+1) + '". '
              if cols[8] == "":
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[8] + '" value expected but not found in cell "' + cellcols[8] + str(i+1) + '". '
    return errormsg

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