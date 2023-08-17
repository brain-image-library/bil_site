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

def check_instrument_sheet(filename):
    instrument_count = 0
    errormsg=""
    workbook=xlrd.open_workbook(filename)
    sheetname = 'Instrument'
    instrument_sheet = workbook.sheet_by_name(sheetname)
    colheads=['MicroscopeType','MicroscopeManufacturerAndModel','ObjectiveName',
                 'ObjectiveImmersion','ObjectiveNA', 'ObjectiveMagnification', 'DetectorType', 'DetectorModel', 'IlluminationTypes', 'IlluminationWavelength', 'DetectionWavelength', 'SampleTemperature']
    cellcols=['A','B','C','D','E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']
    cols=instrument_sheet.row_values(3)
    for i in range(0,len(colheads)):
        if cols[i] != colheads[i]:
            errormsg = errormsg + ' Tab: "Instrument" cell heading found: "' + cols[i] + \
                       '" but expected: "' + colheads[i] + '" at cell: "' + cellcols[i] + '3". '
    if errormsg != "":
        return [ True, errormsg ]
    for i in range(6,instrument_sheet.nrows):
        instrument_count = instrument_count + 1
        cols=instrument_sheet.row_values(i)
        if cols[0] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[0] + '" value expected but not found in cell: "' + cellcols[0] + str(i+1) + '". '
        #if cols[1] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[1] + '" value expected but not found in cell: "' + cellcols[1] + str(i+1) + '". '
        #if cols[2] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[1] + '" value expected but not found in cell: "' + cellcols[1] + str(i+1) + '". '
        #if cols[3] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[3] + '" value expected but not found in cell "' + cellcols[3] + str(i+1) + '". '
        #if cols[4] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[4] + '" value expected but not found in cell "' + cellcols[4] + str(i+1) + '". '
        #if cols[5] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[5] + '" value expected but not found in cell "' + cellcols[5] + str(i+1) + '". '
        #if cols[6] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[6] + '" value expected but not found in cell "' + cellcols[6] + str(i+1) + '". '
        #if cols[7] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[7] + '" value expected but not found in cell "' + cellcols[7] + str(i+1) + '". '
        #if cols[8] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[8] + '" value expected but not found in cell "' + cellcols[8] + str(i+1) + '". '
        #if cols[9] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[9] + '" value expected but not found in cell "' + cellcols[9] + str(i+1) + '". '
        #if cols[10] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[10] + '" value expected but not found in cell "' + cellcols[10] + str(i+1) + '". '
        #if cols[11] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[11] + '" value expected but not found in cell "' + cellcols[11] + str(i+1) + '". '
    return errormsg

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