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

def check_specimen_sheet(filename):
    specimen_count = 0
    errormsg=""
    workbook=xlrd.open_workbook(filename)
    sheetname = 'Specimen'
    specimen_sheet = workbook.sheet_by_name(sheetname)
    colheads=['LocalID', 'Species', 'NCBITaxonomy', 'Age', 'Ageunit', 'Sex', 'Genotype', 'OrganLocalID', 'OrganName', 'SampleLocalID', 'Atlas', 'Locations']
    Sex = ['Male', 'Female', 'Unknown']
    cellcols=['A','B','C','D','E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']
    cols=specimen_sheet.row_values(3)
    for i in range(0,len(colheads)):
        if cols[i] != colheads[i]:
            errormsg = errormsg + ' Tab: "Specimen" cell heading found: "' + cols[i] + \
                       '" but expected: "' + colheads[i] + '" at cell: "' + cellcols[i] + '3". '
    if errormsg != "":
        return [ True, errormsg ]
    for i in range(6,specimen_sheet.nrows):
        specimen_count = specimen_count + 1
        cols=specimen_sheet.row_values(i)
        #if cols[0] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[0] + '" value expected but not found in cell: "' + cellcols[0] + str(i+1) + '". '
        if cols[1] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[1] + '" value expected but not found in cell: "' + cellcols[1] + str(i+1) + '". '
        if cols[2] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[1] + '" value expected but not found in cell: "' + cellcols[1] + str(i+1) + '". '
        if cols[3] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[3] + '" value expected but not found in cell "' + cellcols[3] + str(i+1) + '". '
        if cols[4] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[4] + '" value expected but not found in cell "' + cellcols[4] + str(i+1) + '". '
        if cols[5] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[5] + '" value expected but not found in cell "' + cellcols[5] + str(i+1) + '". '
        if cols[5] not in Sex:
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[5] + '" incorrect CV value found: "' + cols[5] + '" in cell "' + cellcols[6] + str(i+1) + '". '
        #if cols[6] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[6] + '" value expected but not found in cell "' + cellcols[6] + str(i+1) + '". '
        #if cols[7] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[7] + '" value expected but not found in cell "' + cellcols[7] + str(i+1) + '". '
        #if cols[8] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[8] + '" value expected but not found in cell "' + cellcols[8] + str(i+1) + '". '
        if cols[9] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[9] + '" value expected but not found in cell "' + cellcols[9] + str(i+1) + '". '
        #if cols[10] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[10] + '" value expected but not found in cell "' + cellcols[10] + str(i+1) + '". '
        #if cols[11] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[11] + '" value expected but not found in cell "' + cellcols[11] + str(i+1) + '". '
    return errormsg

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