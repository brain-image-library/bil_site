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

def check_funders_sheet(filename):
    errormsg=""
    workbook=xlrd.open_workbook(filename)
    sheetname = 'Funders'
    funders_sheet = workbook.sheet_by_name(sheetname)
    colheads=['funderName','fundingReferenceIdentifier','fundingReferenceIdentifierType',
                 'awardNumber','awardTitle']
    fundingReferenceIdentifierType = ['ROR', 'GRID', 'ORCID', 'ISNI']
    cellcols=['A','B','C','D','E']
    cols=funders_sheet.row_values(3)
    for i in range(0,len(colheads)):
        if cols[i] != colheads[i]:
            errormsg = errormsg + ' Tab: "Funders" cell heading found: "' + cols[i] + \
                       '" but expected: "' + colheads[i] + '" at cell: "' + cellcols[i] + '3". '
    if errormsg != "":
        return [ True, errormsg ]
    for i in range(6,funders_sheet.nrows):
        cols=funders_sheet.row_values(i)
        if cols[0] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[0] + '" value expected but not found in cell: "' + cellcols[0] + str(i+1) + '". '
        
        if cols[1] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[1] + '" value expected but not found in cell: "' + cellcols[1] + str(i+1) + '". '
        if cols[2] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[2] + '" value expected but not found in cell "' + cellcols[2] + str(i+1) + '". '
        if cols[2] not in fundingReferenceIdentifierType:
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[2] + '" incorrect CV value found: "' + cols[2] + '" in cell "' + cellcols[2] + str(i+1) + '". '
        if cols[3] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[3] + '" value expected but not found in cell "' + cellcols[3] + str(i+1) + '". '
        if cols[4] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[4] + '" value expected but not found in cell "' + cellcols[4] + str(i+1) + '". '
    return errormsg

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