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

def check_dataset_sheet(filename):
    dataset_count = 0
    errormsg=""
    workbook=xlrd.open_workbook(filename)
    sheetname = 'Dataset'
    dataset_sheet = workbook.sheet_by_name(sheetname)
    colheads=['BILDirectory','title','socialMedia','subject',
                 'Subjectscheme','rights', 'rightsURI', 'rightsIdentifier', 'Image', 'GeneralModality', 'Technique', 'Other', 'Abstract', 'Methods', 'TechnicalInfo']
    GeneralModality = ['cell morphology', 'connectivity', 'population imaging', 'spatial transcriptomics', 'other', 'anatomy', 'histology imaging', 'multimodal']
    Technique = ['anterograde tracing', 'retrograde transynaptic tracing', 'TRIO tracing', 'smFISH', 'DARTFISH', 'MERFISH', 'Patch-seq', 'fMOST', 'other', 'cre-dependent anterograde tracing','enhancer virus labeling', 'FISH', 'MORF genetic sparse labeling', 'mouselight', 'neuron morphology reconstruction', 'Patch-seq', 'retrograde tracing', 'retrograde transsynaptic tracing', 'seqFISH', 'STPT', 'VISor', 'confocal microscopy']
    cellcols=['A','B','C','D','E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O']
    cols=dataset_sheet.row_values(3)
    for i in range(0,len(colheads)):
        if cols[i] != colheads[i]:
            errormsg = errormsg + ' Tab: "Dataset" cell heading found: "' + cols[i] + \
                       '" but expected: "' + colheads[i] + '" at cell: "' + cellcols[i] + '3". '
    if errormsg != "":
        return [ True, errormsg ]
    for i in range(6,dataset_sheet.nrows):
        dataset_count = dataset_count + 1
        cols=dataset_sheet.row_values(i)
        if cols[0] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[0] + '" value expected but not found in cell: "' + cellcols[0] + str(i+1) + '". '
        if cols[1] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[1] + '" value expected but not found in cell: "' + cellcols[1] + str(i+1) + '". '
        #if cols[2] == "":
             #errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[1] + '" value expected but not found in cell: "' + cellcols[1] + str(i+1) + '". '
        #if cols[3] == "":
            #errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[3] + '" value expected but not found in cell "' + cellcols[3] + str(i+1) + '". '
        #if cols[4] == "":
            #errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[4] + '" value expected but not found in cell "' + cellcols[4] + str(i+1) + '". '
        if cols[5] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[5] + '" value expected but not found in cell "' + cellcols[5] + str(i+1) + '". '
        if cols[6] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[6] + '" value expected but not found in cell "' + cellcols[6] + str(i+1) + '". '
        if cols[7] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[7] + '" value expected but not found in cell "' + cellcols[7] + str(i+1) + '". '
        #if cols[8] == "":
            #errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[8] + '" value expected but not found in cell "' + cellcols[8] + str(i+1) + '". '
        #if cols[9] == "":
            #errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[9] + '" value expected but not found in cell "' + cellcols[9] + str(i+1) + '". '
        if cols[9] != '':
            if cols[9] not in GeneralModality:
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[9] + '" incorrect CV value found: "' + cols[9] + '" in cell "' + cellcols[9] + str(i+1) + '". '
        if cols[10] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[10] + '" value expected but not found in cell "' + cellcols[10] + str(i+1) + '". '
        if cols[10] != '':
            if cols[10] not in Technique:
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[10] + '" incorrect CV value found: "' + cols[10] + '" in cell "' + cellcols[10] + str(i+1) + '". '
        if cols[9] == "other" or cols[10] == "other":
            if cols[11] == "":
        #change to if GeneralModality and Technique = other
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[11] + '" value expected but not found in cell "' + cellcols[11] + str(i+1) + '". '
        if cols[12] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[12] + '" value expected but not found in cell "' + cellcols[12] + str(i+1) + '". '
        #if cols[13] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[13] + '" value expected but not found in cell "' + cellcols[13] + str(i+1) + '". '
        #if cols[14] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[14] + '" value expected but not found in cell "' + cellcols[14] + str(i+1) + '". '
    return errormsg


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