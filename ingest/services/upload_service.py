"""upload_service.py — V2 metadata upload logic, extracted from descriptive_metadata_upload.

This module is intentionally import-clean: it imports helper functions FROM ingest.views
(not the other way around). views.py uses a local import of this module inside the view
function body to prevent circular imports.
"""
import os
import tempfile
from datetime import datetime

import xlrd

from ingest.models import Dataset, DatasetEventsLog, Specimen
from ingest.views import (
    check_all_sheets,
    ingest_contributors_sheet,
    ingest_dataset_sheet,
    ingest_funders_sheet,
    ingest_image_sheet,
    ingest_instrument_sheet,
    ingest_publication_sheet,
    ingest_spatial_sheet,
    ingest_specimen_sheet,
    ingest_swc_sheet,
    save_all_sheets_method_1,
    save_all_sheets_method_2,
    save_all_sheets_method_3,
    save_all_sheets_method_4,
    save_all_sheets_method_5,
    save_all_sheets_method_6,
    save_bil_ids,
    save_sheet_row,
    save_spatial_sheet,
    save_specimen_ids,
)



def _convert_xlsx_to_xls(xlsx_path: str) -> str:
    """Convert an .xlsx file to .xls using openpyxl + xlwt. Returns path to the .xls file."""
    import openpyxl
    import xlwt

    xls_path = xlsx_path[:-5] + '.xls'
    wb_in = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    wb_out = xlwt.Workbook(encoding='utf-8')

    for sheet_name in wb_in.sheetnames:
        ws_in = wb_in[sheet_name]
        ws_out = wb_out.add_sheet(sheet_name)
        for row_idx, row in enumerate(ws_in.iter_rows(values_only=True)):
            for col_idx, value in enumerate(row):
                if value is not None:
                    ws_out.write(row_idx, col_idx, value)

    wb_in.close()
    wb_out.save(xls_path)
    return xls_path


def execute_v2_upload(filename: str, collection, user, ingest_method: str) -> tuple:
    """Execute a V2 metadata upload for a collection, attributed to user.

    Returns (success: bool, error_message: str | None, sheet_id: int | None).
    Does not interact with the HTTP request — callers handle messages/redirects.

    On success: (True, None, sheet.id)
    On failure: (False, error_message, None)
    """
    if filename.endswith('.xlsx'):
        filename = _convert_xlsx_to_xls(filename)

    import xlrd
    _wb = xlrd.open_workbook(filename)
    _sheet_names = _wb.sheet_names()
    has_spatial = 'Spatial' in _sheet_names
    has_swc = 'SWC' in _sheet_names

    error_map = check_all_sheets(
        filename, ingest_method, collection_data_path=collection.data_path
    )
    if error_map:
        error_keys = list(error_map.keys())[:3]
        summary = '; '.join(
            f"{k}: {error_map[k][0]}" for k in error_keys
        )
        return False, f"Validation errors: {summary}", None

    contributors = ingest_contributors_sheet(filename)
    funders = ingest_funders_sheet(filename)
    publications = ingest_publication_sheet(filename)
    instruments = ingest_instrument_sheet(filename)
    datasets = ingest_dataset_sheet(filename)
    specimen_set = ingest_specimen_sheet(filename)
    has_image = 'Image' in _sheet_names
    images = ingest_image_sheet(filename) if has_image else []
    swcs = ingest_swc_sheet(filename) if has_swc else []
    # Only ingest spatial if Spatial sheet exists AND ingest method supports it
    if has_spatial and ingest_method in ('ingest_1', 'ingest_2', 'ingest_6'):
        spatials = ingest_spatial_sheet(filename)
    else:
        spatials = []

    sheet = save_sheet_row(ingest_method, filename, collection)

    saved = False
    if ingest_method == 'ingest_1':
        saved = save_all_sheets_method_1(
            instruments, specimen_set, images, datasets, sheet,
            contributors, funders, publications,
        )
        if has_spatial:
            ingested_datasets = list(Dataset.objects.filter(sheet=sheet))
            save_spatial_sheet(spatials, sheet, ingested_datasets)
    elif ingest_method == 'ingest_2':
        saved = save_all_sheets_method_2(
            instruments, specimen_set, images, datasets, sheet,
            contributors, funders, publications,
        )
        if has_spatial:
            ingested_datasets = list(Dataset.objects.filter(sheet=sheet))
            save_spatial_sheet(spatials, sheet, ingested_datasets)
    elif ingest_method == 'ingest_3':
        saved = save_all_sheets_method_3(
            instruments, specimen_set, images, datasets, sheet,
            contributors, funders, publications,
        )
    elif ingest_method == 'ingest_4':
        saved = save_all_sheets_method_4(
            instruments, specimen_set, images, datasets, sheet,
            contributors, funders, publications,
        )
    elif ingest_method == 'ingest_5':
        saved = save_all_sheets_method_5(
            instruments, specimen_set, datasets, sheet,
            contributors, funders, publications, swcs,
        )
    elif ingest_method == 'ingest_6':
        saved = save_all_sheets_method_6(
            instruments, specimen_set, datasets, sheet,
            contributors, funders, publications, spatials,
        )
    else:
        return False, f"Unknown ingest method: {ingest_method}", None

    ingested_datasets = Dataset.objects.filter(sheet=sheet)
    ingested_specimens = Specimen.objects.filter(sheet=sheet)

    bil_id_result = save_bil_ids(ingested_datasets, filename)
    if bil_id_result is not None:
        return False, f"BIL ID error: {bil_id_result}", None

    save_specimen_ids(ingested_specimens)

    if not saved:
        return False, f"Error saving metadata (sheet id: {sheet.id}). Contact BIL Support.", None

    now = datetime.now()
    for dataset in Dataset.objects.filter(sheet_id=sheet.id):
        DatasetEventsLog.objects.create(
            dataset_id=dataset,
            collection_id=collection,
            project_id_id=collection.project_id,
            notes='',
            timestamp=now,
            event_type='uploaded',
        )

    return True, None, sheet.id
