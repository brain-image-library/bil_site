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


def check_contributors_sheet(filename):
    errormsg=""
    workbook=xlrd.open_workbook(filename)
    sheetname = 'Contributors'
    contributors_sheet = workbook.sheet_by_name(sheetname)
    colheads=['contributorName','Creator','contributorType',
                 'nameType','nameIdentifier','nameIdentifierScheme',
                 'affiliation', 'affiliationIdentifier', 'affiliationIdentifierScheme']
    creator = ['Yes', 'No']
    contributortype = ['ProjectLeader','ResearchGroup','ContactPerson', 'DataCollector', 'DataCurator', 'ProjectLeader', 'ProjectManager', 'ProjectMember','RelatedPerson', 'Researcher', 'ResearchGroup','Other' ]
    nametype = ['Personal', 'Organizational']
    nameidentifierscheme = ['ORCID','ISNI','ROR','GRID','RRID' ]
    affiliationidentifierscheme = ['ORCID','ISNI','ROR','GRID','RRID' ]
    cellcols=['A','B','C','D','E','F','G','H','I']
    cols=contributors_sheet.row_values(2)
    for i in range(0,len(colheads)):
        if cols[i] != colheads[i]:
            errormsg = errormsg + ' Tab: "Contributors" cell heading found: "' + cols[i] + \
                       '" but expected: "' + colheads[i] + '" at cell: "' + cellcols[i] + '3". '
    if errormsg != "":
        return [ True, errormsg ]
    for i in range(6,contributors_sheet.nrows):
        cols=contributors_sheet.row_values(i)
        if cols[0] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[0] + '" value expected but not found in cell: "' + cellcols[0] + str(i+1) + '". '
        if cols[1] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[1] + '" value expected but not found in cell: "' + cellcols[1] + str(i+1) + '". '
        if cols[1] not in creator:
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[1] + '" incorrect CV value found: "' + cols[1] + '" in cell "' + cellcols[1] + str(i+1) + '". '
        if cols[2] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[2] + '" value expected but not found in cell "' + cellcols[2] + str(i+1) + '". '
        if cols[2] not in contributortype:
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[2] + '" incorrect CV value found: "' + cols[2] + '" in cell "' + cellcols[2] + str(i+1) + '". '
        if cols[3] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[3] + '" value expected but not found in cell "' + cellcols[3] + str(i+1) + '". '
        if cols[3] not in nametype:
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[3] + '" incorrect CV value found: "' + cols[3] + '" in cell "' + cellcols[3] + str(i+1) + '". '
        if cols[3] == "Personal":
            if cols[4] == "":
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[4] + '" value expected but not found in cell "' + cellcols[4] + str(i+1) + '". '
            if cols[5] == "":
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[5] + '" value expected but not found in cell "' + cellcols[5] + str(i+1) + '". '
            if cols[5] not in nameidentifierscheme:
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[5] + '" incorrect CV value found: "' + cols[5] + '" in cell "' + cellcols[5] + str(i+1) + '". '
        #else:
            #check nameIdentifier and nameIdentifierScheme ensure they are empty
        if cols[6] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[6] + '" value expected but not found in cell "' + cellcols[6] + str(i+1) + '". '
        if cols[7] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[7] + '" value expected but not found in cell "' + cellcols[7] + str(i+1) + '". '
        if cols[8] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[8] + '" value expected but not found in cell "' + cellcols[8] + str(i+1) + '". '
        if cols[8] not in affiliationidentifierscheme:
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[8] + '" Incorrect CV value found: "' + cols[8] + '" in cell "' + cellcols[8] + str(i+1) + '". '
    return errormsg


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