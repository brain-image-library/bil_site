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

def check_image_sheet(filename):
    image_count = 0
    errormsg=""
    workbook=xlrd.open_workbook(filename)
    sheetname = 'Image'
    image_sheet = workbook.sheet_by_name(sheetname)
    colheads=['xAxis','obliqueXdim1','obliqueXdim2',
                 'obliqueXdim3','yAxis', 'obliqueYdim1', 'obliqueYdim2', 'obliqueYdim3', 'zAxis', 'obliqueZdim1', 'obliqueZdim2', 'obliqueZdim3', 'landmarkName', 'landmarkX', 'landmarkY', 'landmarkZ', 'Number', 'displayColor', 'Representation', 'Flurophore', 'stepSizeX', 'stepSizeY', 'stepSizeZ', 'stepSizeT', 'Channels', 'Slices', 'z', 'Xsize', 'Ysize', 'Zsize', 'Gbytes', 'Files', 'DimensionOrder']
    ObliqueZdim3 = ['Superior', 'Inferior']
    ObliqueZdim2 = ['Anterior', 'Posterior']
    ObliqueZdim1 = ['Right', 'Left']
    zAxis = ['right-to-left', 'left-to-right', 'anterior-to-posterior', 'posterior-to-anterior', 'superior-to-inferior', 'inferior-to-superior', 'oblique',  'NA', 'N/A', 'na', 'N/A']
    obliqueYdim3 = ['Superior', 'Inferior']
    obliqueYdim2 = ['Anterior', 'Posterior']
    obliqueYdim1 = ['Right', 'Left']
    yAxis = ['right-to-left', 'left-to-right', 'anterior-to-posterior', 'posterior-to-anterior', 'superior-to-inferior', 'inferior-to-superior', 'oblique',  'NA', 'N/A', 'na', 'N/A']
    obliqueXdim3 = ['Superior', 'Inferior']
    obliqueXdim2 = ['Anterior', 'Posterior']
    obliqueXdim1 = ['Right', 'Left']
    xAxis = ['right-to-left', 'left-to-right', 'anterior-to-posterior', 'posterior-to-anterior', 'superior-to-inferior', 'inferior-to-superior', 'oblique', 'NA', 'N/A', 'na', 'N/A']

    cellcols=['A','B','C','D','E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', 'AA', 'AB', 'AC', 'AD', 'AE', 'AF', 'AG']
    cols=image_sheet.row_values(3)
    for i in range(0,len(colheads)):
        if cols[i] != colheads[i]:
            errormsg = errormsg + ' Tab: "Image" cell heading found: "' + cols[i] + \
                       '" but expected: "' + colheads[i] + '" at cell: "' + cellcols[i] + '3". '
    if errormsg != "":
        return [ True, errormsg ]
    for i in range(6,image_sheet.nrows):
        image_count = image_count + 1
        cols=image_sheet.row_values(i)
        #if xAxis is oblique, oblique cols should reflect 
        if cols[0] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname + 'Column: "' + colheads[0] + '" value expected but not found in cell: "' + cellcols[0] + str(i+1) + '". '
        if cols[0] not in xAxis:
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname + 'Column: "' + colheads[0] + '" incorrect CV value found: "' + cols[0] + '" in cell "' + cellcols[0] + str(i+1) + '". '
        #if cols[1] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname + 'Column: "' + colheads[1] + '" value expected but not found in cell: "' + cellcols[1] + str(i+1) + '". '
        if cols[1] != "":
            if cols[1] not in obliqueXdim1:
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[1] + '" incorrect CV value found: "' + cols[1] + '" in cell "' + cellcols[1] + str(i+1) + '". '
        #if cols[2] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[1] + '" value expected but not found in cell: "' + cellcols[2] + str(i+1) + '". '
        if cols[2] != "":
            if cols[2] not in obliqueXdim2:
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[2] + '" incorrect CV value found: "' + cols[2] + '" in cell "' + cellcols[2] + str(i+1) + '". '
        #if cols[3] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[3] + '" value expected but not found in cell "' + cellcols[3] + str(i+1) + '". '
        if cols[3] != "":
            if cols[3] not in obliqueXdim3:
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[3] + '" incorrect CV value found: "' + cols[3] + '" in cell "' + cellcols[3] + str(i+1) + '". '
        if cols[4] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[4] + '" value expected but not found in cell "' + cellcols[4] + str(i+1) + '". '
        if cols[4] not in yAxis:
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[4] + '" incorrect CV value found: "' + cols[4] + '" in cell "' + cellcols[4] + str(i+1) + '". '
        #if cols[5] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[5] + '" value expected but not found in cell "' + cellcols[5] + str(i+1) + '". '
        if cols[5] != "":
            if cols[5] not in obliqueYdim1:
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[5] + '" incorrect CV value found: "' + cols[5] + '" in cell "' + cellcols[5] + str(i+1) + '". '
        #if cols[6] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[6] + '" value expected but not found in cell "' + cellcols[6] + str(i+1) + '". '
        if cols[6] != "":
            if cols[6] not in obliqueYdim2:
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[6] + '" incorrect CV value found: "' + cols[6] + '" in cell "' + cellcols[6] + str(i+1) + '". '
        #if cols[7] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[7] + '" value expected but not found in cell "' + cellcols[7] + str(i+1) + '". '
        if cols[7] != "":
            if cols[7] not in obliqueYdim3:
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[7] + '" incorrect CV value found: "' + cols[7] + '" in cell "' + cellcols[7] + str(i+1) + '". '
        if cols[8] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[8] + '" value expected but not found in cell "' + cellcols[8] + str(i+1) + '". '
        if cols[8] not in zAxis:
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[8] + '" incorrect CV value found: "' + cols[8] + '" in cell "' + cellcols[8] + str(i+1) + '". '
        #if cols[9] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[9] + '" value expected but not found in cell "' + cellcols[9] + str(i+1) + '". '
        if cols[9] != "":
            if cols[9] not in ObliqueZdim1:
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[9] + '" incorrect CV value found: "' + cols[9] + '" in cell "' + cellcols[9] + str(i+1) + '". '
        #if cols[10] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[10] + '" value expected but not found in cell "' + cellcols[10] + str(i+1) + '". '
        if cols[10] != "":
            if cols[10] not in ObliqueZdim2:
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[10] + '" incorrect CV value found: "' + cols[10] + '" in cell "' + cellcols[10] + str(i+1) + '". '
        #if cols[11] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[11] + '" value expected but not found in cell "' + cellcols[11] + str(i+1) + '". '
        if cols[11] != "":
            if cols[11] not in ObliqueZdim3:
                errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[11] + '" incorrect CV value found: "' + cols[11] + '" in cell "' + cellcols[11] + str(i+1) + '". '
        #if cols[12] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[12] + '" value expected but not found in cell "' + cellcols[12] + str(i+1) + '". '
        #if cols[13] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[13] + '" value expected but not found in cell "' + cellcols[13] + str(i+1) + '". '
        #if cols[14] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[12] + '" value expected but not found in cell "' + cellcols[12] + str(i+1) + '". '
        # if cols[15] == "":
        #     errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[15] + '" value expected but not found in cell "' + cellcols[15] + str(i+1) + '". '
        if cols[16] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[12] + '" value expected but not found in cell "' + cellcols[12] + str(i+1) + '". '
        if cols[17] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[12] + '" value expected but not found in cell "' + cellcols[12] + str(i+1) + '". '
        #if cols[18] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[18] + '" value expected but not found in cell "' + cellcols[18] + str(i+1) + '". '
        #if cols[19] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[12] + '" value expected but not found in cell "' + cellcols[12] + str(i+1) + '". '
        if cols[20] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[20] + '" value expected but not found in cell "' + cellcols[20] + str(i+1) + '". '
        if cols[21] == "":
            errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[21] + '" value expected but not found in cell "' + cellcols[21] + str(i+1) + '". '
        #if cols[22] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[22] + '" value expected but not found in cell "' + cellcols[22] + str(i+1) + '". '
        #if cols[23] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[23] + '" value expected but not found in cell "' + cellcols[23] + str(i+1) + '". '
        #if cols[24] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[24] + '" value expected but not found in cell "' + cellcols[24] + str(i+1) + '". '
        #if cols[25] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[25] + '" value expected but not found in cell "' + cellcols[25] + str(i+1) + '". '
        #if cols[26] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[26] + '" value expected but not found in cell "' + cellcols[26] + str(i+1) + '". '
        #if cols[27] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[27] + '" value expected but not found in cell "' + cellcols[27] + str(i+1) + '". '
        #if cols[28] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[28] + '" value expected but not found in cell "' + cellcols[28] + str(i+1) + '". '
        #if cols[29] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[29] + '" value expected but not found in cell "' + cellcols[29] + str(i+1) + '". '
        #if cols[30] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[30] + '" value expected but not found in cell "' + cellcols[30] + str(i+1) + '". '
        #if cols[31] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[31] + '" value expected but not found in cell "' + cellcols[31] + str(i+1) + '". '
        #if cols[32] == "":
        #    errormsg = errormsg + 'On spreadsheet tab:' + sheetname +  'Column: "' + colheads[32] + '" value expected but not found in cell "' + cellcols[32] + str(i+1) + '". '
    return errormsg


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
