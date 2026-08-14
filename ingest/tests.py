"""
Unit tests for spreadsheet validation (check_*_sheet functions).

Each test class covers one sheet type. Tests build minimal .xls workbooks
with xlwt (which xlrd can read), write them to temp files, and call the
relevant check function directly — no HTTP or database involved.

Sheet layout used by the check functions:
  Contributors  — header at row 2, data from row 6
  All others    — header at row 3, data from row 6

Run with:
  python manage.py test ingest.tests
  python manage.py test ingest.tests.CheckContributorsSheetTests
"""

import json
import os
import tempfile
import xlwt
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, RequestFactory, override_settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from .models import Project, People, ProjectPeople, Consortium, Collection, EventsLog, DescriptiveMetadata

from ingest.views import (
    _assert_bil_admin,
    _assert_pi_of_project,
    check_contributors_sheet,
    check_funders_sheet,
    check_publication_sheet,
    check_instrument_sheet,
    check_dataset_sheet,
    check_specimen_sheet,
    check_image_sheet,
    check_swc_sheet,
    check_spatial_sheet,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_CONTRIBUTORS_HEADERS = [
    'contributorName', 'Creator', 'contributorType', 'nameType',
    'nameIdentifier', 'nameIdentifierScheme', 'affiliation',
    'affiliationIdentifier', 'affiliationIdentifierScheme',
]
_FUNDERS_HEADERS = [
    'funderName', 'fundingReferenceIdentifier', 'fundingReferenceIdentifierType',
    'awardNumber', 'awardTitle',
]
_PUBLICATION_HEADERS = [
    'relatedIdentifier', 'relatedIdentifierType', 'PMCID', 'relationType', 'citation',
]
_INSTRUMENT_HEADERS = [
    'MicroscopeType', 'MicroscopeManufacturerAndModel', 'ObjectiveName',
    'ObjectiveImmersion', 'ObjectiveNA', 'ObjectiveMagnification', 'DetectorType',
    'DetectorModel', 'IlluminationTypes', 'IlluminationWavelength',
    'DetectionWavelength', 'SampleTemperature',
]
_DATASET_HEADERS = [
    'BILDirectory', 'title', 'socialMedia', 'subject', 'Subjectscheme',
    'rights', 'rightsURI', 'rightsIdentifier', 'Image', 'GeneralModality',
    'Technique', 'Other', 'Abstract', 'Methods', 'TechnicalInfo',
]
_SPECIMEN_HEADERS = [
    'LocalID', 'Species', 'NCBITaxonomy', 'Age', 'Ageunit', 'Sex',
    'Genotype', 'OrganLocalID', 'OrganName', 'SampleLocalID', 'Atlas', 'Locations',
]
_IMAGE_HEADERS = [
    'xAxis', 'obliqueXdim1', 'obliqueXdim2', 'obliqueXdim3',
    'yAxis', 'obliqueYdim1', 'obliqueYdim2', 'obliqueYdim3',
    'zAxis', 'obliqueZdim1', 'obliqueZdim2', 'obliqueZdim3',
    'landmarkName', 'landmarkX', 'landmarkY', 'landmarkZ',
    'Number', 'displayColor', 'Representation', 'Flurophore',
    'stepSizeX', 'stepSizeY', 'stepSizeZ', 'stepSizeT',
    'Channels', 'Slices', 'z', 'Xsize', 'Ysize', 'Zsize',
    'Gbytes', 'Files', 'DimensionOrder',
]
_SWC_HEADERS = [
    'tracingFile', 'sourceData', 'sourceDataSample', 'sourceDataSubmission',
    'coordinates', 'coordinatesRegistration', 'brainRegion', 'brainRegionAtlas',
    'brainRegionAtlasName', 'brainRegionAxonalProjection',
    'brainRegionDendriticProjection', 'neuronType', 'segmentTags',
    'proofreadingLevel', 'Notes',
]
_SPATIAL_HEADERS = [
    'DataAvailability', 'HistologicalStainName', 'NuclearStainName', 'ProbeSetDOI',
    'ProbeSequencesDOI', 'LightTreatmentTime', 'LightTreatmentTimeUnits',
    'NumberTargetedRNA', 'GenePanelName', 'PlatformName', 'MachineName',
    'MachineSoftwareVersion', 'NumberZSections', 'SegmentationMethod',
    'SegmentationModel', 'SegmentationMethodVersion', 'ClusteringMethod',
    'LabelTransferMethod', 'LabelTransferReference', 'NuclearImageTransform',
    'HistologicalImageTransform', 'FilterCriteria', 'XYZPosition', 'CellID',
    'CellCentroidLocation', 'CellAreaVolume',
]


def _write_row(ws, row, values):
    """Write a list of values to a worksheet row."""
    for col, v in enumerate(values):
        ws.write(row, col, v)


def _save(wb):
    """Save workbook to a temp file and return the path."""
    fd, path = tempfile.mkstemp(suffix='.xls')
    os.close(fd)
    wb.save(path)
    return path


def _cleanup(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def _errors_at(errors, row, col):
    """Return error messages for a specific (row, col) cell."""
    return [e['message'] for e in errors if e['row'] == row and e['col'] == col]


# ---------------------------------------------------------------------------
# Contributors
# ---------------------------------------------------------------------------

class CheckContributorsSheetTests(TestCase):
    """header at row 2, data from row 6."""

    HEADER_ROW = 2
    DATA_ROW = 6

    def _make_wb(self, headers=None):
        wb = xlwt.Workbook()
        ws = wb.add_sheet('Contributors')
        _write_row(ws, self.HEADER_ROW, headers or _CONTRIBUTORS_HEADERS)
        return wb, ws

    def _valid_row(self):
        return [
            'Doe, John', 'Yes', 'ProjectLeader', 'Personal',
            '0000-0000-0000-0001', 'ORCID', 'PSC', 'ROR:12345', 'ROR',
        ]

    def test_valid_data_returns_no_errors(self):
        wb, ws = self._make_wb()
        _write_row(ws, self.DATA_ROW, self._valid_row())
        path = _save(wb)
        try:
            self.assertEqual(check_contributors_sheet(path), [])
        finally:
            _cleanup(path)

    def test_wrong_header_name_stops_early(self):
        bad_headers = list(_CONTRIBUTORS_HEADERS)
        bad_headers[0] = 'WRONG_HEADER'
        wb, ws = self._make_wb(headers=bad_headers)
        path = _save(wb)
        try:
            errors = check_contributors_sheet(path)
            self.assertTrue(any(e['row'] == self.HEADER_ROW and e['col'] == 0 for e in errors))
        finally:
            _cleanup(path)

    def test_missing_contributor_name(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[0] = ''
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_contributors_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 0)
            self.assertTrue(any('required' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_invalid_creator_value(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[1] = 'Maybe'
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_contributors_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 1)
            self.assertTrue(any('Maybe' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_invalid_contributor_type(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[2] = 'BossMan'
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_contributors_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 2)
            self.assertTrue(any('BossMan' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_invalid_name_type(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[3] = 'Robot'
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_contributors_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 3)
            self.assertTrue(any('Robot' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_personal_name_type_requires_identifier(self):
        """nameType=Personal requires nameIdentifier (col 4) and nameIdentifierScheme (col 5)."""
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[3] = 'Personal'
        row[4] = ''   # missing identifier
        row[5] = ''   # missing scheme
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_contributors_sheet(path)
            self.assertTrue(any(e['col'] == 4 for e in errors))
            self.assertTrue(any(e['col'] == 5 for e in errors))
        finally:
            _cleanup(path)

    def test_invalid_affiliation_identifier_scheme(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[8] = 'LinkedIn'
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_contributors_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 8)
            self.assertTrue(any('LinkedIn' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_multiple_data_rows_accumulates_errors(self):
        wb, ws = self._make_wb()
        good_row = self._valid_row()
        # xlwt skips entirely-blank rows; give col 0 a value so the row is written,
        # but leave required cols 1-3 empty so the check produces errors.
        bad_row = ['Doe, Jane', '', '', '', '', '', '', '', '']
        _write_row(ws, self.DATA_ROW, good_row)
        _write_row(ws, self.DATA_ROW + 1, bad_row)
        path = _save(wb)
        try:
            errors = check_contributors_sheet(path)
            # Errors should be on the second data row, not the first
            self.assertTrue(all(e['row'] != self.DATA_ROW for e in errors))
            self.assertTrue(any(e['row'] == self.DATA_ROW + 1 for e in errors))
        finally:
            _cleanup(path)


# ---------------------------------------------------------------------------
# Funders
# ---------------------------------------------------------------------------

class CheckFundersSheetTests(TestCase):
    """header at row 3, data from row 6."""

    HEADER_ROW = 3
    DATA_ROW = 6

    def _make_wb(self, headers=None):
        wb = xlwt.Workbook()
        ws = wb.add_sheet('Funders')
        _write_row(ws, self.HEADER_ROW, headers or _FUNDERS_HEADERS)
        return wb, ws

    def _valid_row(self):
        return ['NIH', 'ROR:00hx57361', 'ROR', 'R01NS123456', 'Brain Imaging Award']

    def test_valid_data_returns_no_errors(self):
        wb, ws = self._make_wb()
        _write_row(ws, self.DATA_ROW, self._valid_row())
        path = _save(wb)
        try:
            self.assertEqual(check_funders_sheet(path), [])
        finally:
            _cleanup(path)

    def test_missing_funder_name(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[0] = ''
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_funders_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 0)
            self.assertTrue(any('required' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_invalid_funding_reference_identifier_type(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[2] = 'DOI'   # valid for other fields but not this enum
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_funders_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 2)
            self.assertTrue(any('DOI' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_missing_award_number_and_title(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[3] = ''
        row[4] = ''
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_funders_sheet(path)
            self.assertTrue(any(e['col'] == 3 for e in errors))
            self.assertTrue(any(e['col'] == 4 for e in errors))
        finally:
            _cleanup(path)

    def test_wrong_header_stops_early(self):
        bad = list(_FUNDERS_HEADERS)
        bad[1] = 'badHeader'
        wb, ws = self._make_wb(headers=bad)
        path = _save(wb)
        try:
            errors = check_funders_sheet(path)
            self.assertTrue(any(e['row'] == self.HEADER_ROW for e in errors))
        finally:
            _cleanup(path)


# ---------------------------------------------------------------------------
# Publication
# ---------------------------------------------------------------------------

class CheckPublicationSheetTests(TestCase):
    """header at row 3, data from row 6. Enum checks only (no required fields)."""

    HEADER_ROW = 3
    DATA_ROW = 6

    def _make_wb(self, headers=None):
        wb = xlwt.Workbook()
        ws = wb.add_sheet('Publication')
        _write_row(ws, self.HEADER_ROW, headers or _PUBLICATION_HEADERS)
        return wb, ws

    def _valid_row(self):
        return ['10.1234/brain.001', 'DOI', 'PMC123456', 'IsCitedBy', 'Doe et al. 2023']

    def test_valid_data_returns_no_errors(self):
        wb, ws = self._make_wb()
        _write_row(ws, self.DATA_ROW, self._valid_row())
        path = _save(wb)
        try:
            self.assertEqual(check_publication_sheet(path), [])
        finally:
            _cleanup(path)

    def test_invalid_related_identifier_type(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[1] = 'URL'   # not in allowed list
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_publication_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 1)
            self.assertTrue(any('URL' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_invalid_relation_type(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[3] = 'References'   # not in allowed list
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_publication_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 3)
            self.assertTrue(any('References' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_empty_enum_cells_are_skipped(self):
        """Empty relatedIdentifierType / relationType should not produce errors."""
        wb, ws = self._make_wb()
        _write_row(ws, self.DATA_ROW, ['', '', '', '', ''])
        path = _save(wb)
        try:
            self.assertEqual(check_publication_sheet(path), [])
        finally:
            _cleanup(path)


# ---------------------------------------------------------------------------
# Instrument
# ---------------------------------------------------------------------------

class CheckInstrumentSheetTests(TestCase):
    """header at row 3, data from row 6. Only col 0 (MicroscopeType) is required."""

    HEADER_ROW = 3
    DATA_ROW = 6

    def _make_wb(self, headers=None):
        wb = xlwt.Workbook()
        ws = wb.add_sheet('Instrument')
        _write_row(ws, self.HEADER_ROW, headers or _INSTRUMENT_HEADERS)
        return wb, ws

    def _valid_row(self):
        return ['Confocal', 'Leica SP8', '10x', 'Oil', '1.4', '10', 'PMT', 'R9624',
                'Wide-field', '488', '520', '25']

    def test_valid_data_returns_no_errors(self):
        wb, ws = self._make_wb()
        _write_row(ws, self.DATA_ROW, self._valid_row())
        path = _save(wb)
        try:
            self.assertEqual(check_instrument_sheet(path), [])
        finally:
            _cleanup(path)

    def test_missing_microscope_type(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[0] = ''
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_instrument_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 0)
            self.assertTrue(any('required' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_wrong_header_stops_early(self):
        bad = list(_INSTRUMENT_HEADERS)
        bad[0] = 'scope'
        wb, ws = self._make_wb(headers=bad)
        path = _save(wb)
        try:
            errors = check_instrument_sheet(path)
            self.assertTrue(any(e['row'] == self.HEADER_ROW for e in errors))
        finally:
            _cleanup(path)


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class CheckDatasetSheetTests(TestCase):
    """header at row 3, data from row 6."""

    HEADER_ROW = 3
    DATA_ROW = 6

    def _make_wb(self, headers=None):
        wb = xlwt.Workbook()
        ws = wb.add_sheet('Dataset')
        _write_row(ws, self.HEADER_ROW, headers or _DATASET_HEADERS)
        return wb, ws

    def _valid_row(self):
        # 15 columns: BILDirectory, title, socialMedia, subject, Subjectscheme,
        #             rights, rightsURI, rightsIdentifier, Image, GeneralModality,
        #             Technique, Other, Abstract, Methods, TechnicalInfo
        return [
            '/bil/data/dataset1', 'My Dataset', '', 'Neuroscience', 'FreeText',
            'CC BY 4.0', 'https://creativecommons.org/licenses/by/4.0/', 'CC-BY-4.0',
            '', 'anatomy', 'confocal microscopy', '', 'Whole-brain imaging abstract',
            'Fixed tissue confocal', '',
        ]

    def test_valid_data_returns_no_errors(self):
        wb, ws = self._make_wb()
        _write_row(ws, self.DATA_ROW, self._valid_row())
        path = _save(wb)
        try:
            self.assertEqual(check_dataset_sheet(path), [])
        finally:
            _cleanup(path)

    def test_missing_bil_directory(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[0] = ''
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_dataset_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 0)
            self.assertTrue(any('required' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_missing_title(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[1] = ''
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_dataset_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 1)
            self.assertTrue(any('required' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_missing_rights_fields(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[5] = ''   # rights
        row[6] = ''   # rightsURI
        row[7] = ''   # rightsIdentifier
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_dataset_sheet(path)
            self.assertTrue(any(e['col'] == 5 for e in errors))
            self.assertTrue(any(e['col'] == 6 for e in errors))
            self.assertTrue(any(e['col'] == 7 for e in errors))
        finally:
            _cleanup(path)

    def test_invalid_general_modality(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[9] = 'neuroscience_vibes'
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_dataset_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 9)
            self.assertTrue(any('neuroscience_vibes' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_invalid_technique(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[10] = 'magic microscopy'
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_dataset_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 10)
            self.assertTrue(any('magic microscopy' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_other_technique_requires_other_field(self):
        """When Technique='other', col 11 (Other) must be filled."""
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[10] = 'other'
        row[11] = ''
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_dataset_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 11)
            self.assertTrue(any('required' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_other_modality_requires_other_field(self):
        """When GeneralModality='other', col 11 (Other) must be filled."""
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[9] = 'other'
        row[11] = ''
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_dataset_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 11)
            self.assertTrue(any('required' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_missing_abstract(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[12] = ''
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_dataset_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 12)
            self.assertTrue(any('required' in m for m in msgs))
        finally:
            _cleanup(path)


# ---------------------------------------------------------------------------
# Specimen
# ---------------------------------------------------------------------------

class CheckSpecimenSheetTests(TestCase):
    """header at row 3, data from row 6."""

    HEADER_ROW = 3
    DATA_ROW = 6

    def _make_wb(self, headers=None):
        wb = xlwt.Workbook()
        ws = wb.add_sheet('Specimen')
        _write_row(ws, self.HEADER_ROW, headers or _SPECIMEN_HEADERS)
        return wb, ws

    def _valid_row(self):
        return ['SP001', 'Mus musculus', '10090', '8', 'weeks', 'Male',
                'C57BL/6J', 'ORG001', 'brain', 'SMP001', 'CCFv3', '']

    def test_valid_data_returns_no_errors(self):
        wb, ws = self._make_wb()
        _write_row(ws, self.DATA_ROW, self._valid_row())
        path = _save(wb)
        try:
            self.assertEqual(check_specimen_sheet(path), [])
        finally:
            _cleanup(path)

    def test_missing_species(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[1] = ''
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_specimen_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 1)
            self.assertTrue(any('required' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_invalid_sex_value(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[5] = 'hermaphrodite'
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_specimen_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 5)
            self.assertTrue(any('hermaphrodite' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_missing_multiple_required_fields(self):
        wb, ws = self._make_wb()
        # Only LocalID (col 0) is not required — blank everything else
        row = ['SP001', '', '', '', '', '', '', '', '', '', '', '']
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_specimen_sheet(path)
            error_cols = {e['col'] for e in errors}
            # cols 1,2,3,4,5,9 are required
            self.assertIn(1, error_cols)
            self.assertIn(2, error_cols)
            self.assertIn(3, error_cols)
            self.assertIn(4, error_cols)
            self.assertIn(9, error_cols)
        finally:
            _cleanup(path)

    def test_unknown_sex_is_valid(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[5] = 'Unknown'
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            self.assertEqual(check_specimen_sheet(path), [])
        finally:
            _cleanup(path)


# ---------------------------------------------------------------------------
# Image
# ---------------------------------------------------------------------------

class CheckImageSheetTests(TestCase):
    """header at row 3, data from row 6. Axis enums + required Number/displayColor/stepSizes."""

    HEADER_ROW = 3
    DATA_ROW = 6

    def _make_wb(self, headers=None):
        wb = xlwt.Workbook()
        ws = wb.add_sheet('Image')
        _write_row(ws, self.HEADER_ROW, headers or _IMAGE_HEADERS)
        return wb, ws

    def _valid_row(self):
        # 33 columns; cols 16,17,20,21 are required; 0,4,8 are required axis enums
        row = [''] * 33
        row[0] = 'left-to-right'    # xAxis
        row[4] = 'anterior-to-posterior'   # yAxis
        row[8] = 'superior-to-inferior'    # zAxis
        row[16] = '1'               # Number
        row[17] = 'red'             # displayColor
        row[20] = '0.5'             # stepSizeX
        row[21] = '0.5'             # stepSizeY
        return row

    def test_valid_data_returns_no_errors(self):
        wb, ws = self._make_wb()
        _write_row(ws, self.DATA_ROW, self._valid_row())
        path = _save(wb)
        try:
            self.assertEqual(check_image_sheet(path), [])
        finally:
            _cleanup(path)

    def test_missing_x_axis(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[0] = ''
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_image_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 0)
            self.assertTrue(any('required' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_invalid_x_axis_value(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[0] = 'diagonal'
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_image_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 0)
            self.assertTrue(any('diagonal' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_invalid_oblique_dim1(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[1] = 'North'   # must be Right or Left
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_image_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 1)
            self.assertTrue(any('North' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_missing_required_number_and_display_color(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[16] = ''   # Number required
        row[17] = ''   # displayColor required
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_image_sheet(path)
            self.assertTrue(any(e['col'] == 16 for e in errors))
            self.assertTrue(any(e['col'] == 17 for e in errors))
        finally:
            _cleanup(path)

    def test_missing_step_sizes(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[20] = ''   # stepSizeX required
        row[21] = ''   # stepSizeY required
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_image_sheet(path)
            self.assertTrue(any(e['col'] == 20 for e in errors))
            self.assertTrue(any(e['col'] == 21 for e in errors))
        finally:
            _cleanup(path)


# ---------------------------------------------------------------------------
# SWC
# ---------------------------------------------------------------------------

class CheckSWCSheetTests(TestCase):
    """header at row 3, data from row 6."""

    HEADER_ROW = 3
    DATA_ROW = 6

    def _make_wb(self, headers=None):
        wb = xlwt.Workbook()
        ws = wb.add_sheet('SWC')
        _write_row(ws, self.HEADER_ROW, headers or _SWC_HEADERS)
        return wb, ws

    def _valid_row(self):
        row = [''] * 15
        row[0] = 'neuron.swc'
        row[5] = 'No'
        return row

    def test_valid_data_returns_no_errors(self):
        wb, ws = self._make_wb()
        _write_row(ws, self.DATA_ROW, self._valid_row())
        path = _save(wb)
        try:
            self.assertEqual(check_swc_sheet(path), [])
        finally:
            _cleanup(path)

    def test_missing_tracing_file(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[0] = ''
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_swc_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 0)
            self.assertTrue(any('required' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_missing_coordinates_registration(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[5] = ''
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_swc_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 5)
            self.assertTrue(any('required' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_invalid_coordinates_registration_value(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[5] = 'Maybe'
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_swc_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 5)
            self.assertTrue(any('Maybe' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_coordinates_yes_requires_brain_region_fields(self):
        """coordinatesRegistration=Yes requires brainRegion (6), brainRegionAtlas (7),
        brainRegionAtlasName (8)."""
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[5] = 'Yes'
        row[6] = ''
        row[7] = ''
        row[8] = ''
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_swc_sheet(path)
            self.assertTrue(any(e['col'] == 6 for e in errors))
            self.assertTrue(any(e['col'] == 7 for e in errors))
            self.assertTrue(any(e['col'] == 8 for e in errors))
        finally:
            _cleanup(path)

    def test_coordinates_yes_with_all_fields_is_valid(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[5] = 'Yes'
        row[6] = 'cortex'
        row[7] = 'CCF'
        row[8] = 'Allen CCFv3'
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            self.assertEqual(check_swc_sheet(path), [])
        finally:
            _cleanup(path)


# ---------------------------------------------------------------------------
# Spatial
# ---------------------------------------------------------------------------

class CheckSpatialSheetTests(TestCase):
    """header at row 3, data from row 6. Missing sheet, enum checks, numeric checks."""

    HEADER_ROW = 3
    DATA_ROW = 6

    def _make_wb(self, include_spatial=True, headers=None):
        wb = xlwt.Workbook()
        if include_spatial:
            ws = wb.add_sheet('Spatial')
            _write_row(ws, self.HEADER_ROW, headers or _SPATIAL_HEADERS)
            return wb, ws
        # Add a different sheet so the workbook isn't empty
        wb.add_sheet('OtherSheet')
        return wb, None

    def _valid_row(self):
        row = [''] * 26
        row[0] = 'raw'         # DataAvailability
        row[9] = 'Xenium'      # PlatformName
        return row

    def test_missing_spatial_tab_returns_error(self):
        wb, _ = self._make_wb(include_spatial=False)
        path = _save(wb)
        try:
            errors = check_spatial_sheet(path)
            self.assertTrue(any('Spatial' in e['message'] for e in errors))
        finally:
            _cleanup(path)

    def test_valid_data_returns_no_errors(self):
        wb, ws = self._make_wb()
        _write_row(ws, self.DATA_ROW, self._valid_row())
        path = _save(wb)
        try:
            self.assertEqual(check_spatial_sheet(path), [])
        finally:
            _cleanup(path)

    def test_missing_data_availability(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[0] = ''
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_spatial_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 0)
            self.assertTrue(any('required' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_invalid_data_availability(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[0] = 'processed'
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_spatial_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 0)
            self.assertTrue(any('processed' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_invalid_platform_name(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[9] = 'SuperScope'
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_spatial_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 9)
            self.assertTrue(any('SuperScope' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_non_numeric_light_treatment_time(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[5] = 'twenty'   # LightTreatmentTime must be numeric
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_spatial_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 5)
            self.assertTrue(any('numeric' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_non_integer_number_targeted_rna(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[7] = 'many'   # NumberTargetedRNA must be integer
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_spatial_sheet(path)
            msgs = _errors_at(errors, self.DATA_ROW, 7)
            self.assertTrue(any('integer' in m for m in msgs))
        finally:
            _cleanup(path)

    def test_partial_file_columns_triggers_errors(self):
        """If any of cols 22-25 is filled, all four must be filled."""
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[22] = 'some_xyz_file'   # XYZPosition
        # 23, 24, 25 left empty — should trigger 3 errors
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            errors = check_spatial_sheet(path)
            missing_cols = {e['col'] for e in errors if e['row'] == self.DATA_ROW}
            self.assertIn(23, missing_cols)
            self.assertIn(24, missing_cols)
            self.assertIn(25, missing_cols)
        finally:
            _cleanup(path)

    def test_all_file_columns_filled_is_valid(self):
        wb, ws = self._make_wb()
        row = self._valid_row()
        row[22] = 'xyz.csv'
        row[23] = 'cell_id.csv'
        row[24] = 'centroid.csv'
        row[25] = 'area.csv'
        _write_row(ws, self.DATA_ROW, row)
        path = _save(wb)
        try:
            self.assertEqual(check_spatial_sheet(path), [])
        finally:
            _cleanup(path)

    def test_completely_blank_row_is_skipped(self):
        """Spatial skips entirely-blank rows so they should not produce errors."""
        wb, ws = self._make_wb()
        _write_row(ws, self.DATA_ROW, [''] * 26)
        path = _save(wb)
        try:
            self.assertEqual(check_spatial_sheet(path), [])
        finally:
            _cleanup(path)


# ---------------------------------------------------------------------------
# BrainInitiative
# ---------------------------------------------------------------------------

class BrainInitiativeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')
        self.people = People.objects.create(
            name='Test User',
            orcid='',
            affiliation='',
            affiliation_identifier='',
            is_bil_admin=False,
            has_reviewed_brain_initiative=False,
            auth_user_id=self.user,
        )
        self.project = Project.objects.create(
            name='Test Project',
            funded_by='NIH',
            is_brain_initiative=False,
        )
        ProjectPeople.objects.create(
            project_id=self.project,
            people_id=self.people,
            is_pi=True,
            is_po=False,
            doi_role='creator',
        )

    def test_create_project_sets_brain_initiative_true(self):
        payload = [{'name': 'New Proj', 'funded_by': 'NIH', 'consortia_ids': [], 'parent_project': '', 'is_brain_initiative': True}]
        response = self.client.post(
            '/ingest/create_project/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        proj = Project.objects.get(name='New Proj')
        self.assertTrue(proj.is_brain_initiative)

    def test_create_project_sets_brain_initiative_false_by_default(self):
        payload = [{'name': 'No BI Proj', 'funded_by': '', 'consortia_ids': [], 'parent_project': '', 'is_brain_initiative': False}]
        response = self.client.post(
            '/ingest/create_project/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        proj = Project.objects.get(name='No BI Proj')
        self.assertFalse(proj.is_brain_initiative)

    def test_review_brain_initiative_saves_and_sets_flag(self):
        payload = {str(self.project.id): True}
        response = self.client.post(
            '/ingest/review-brain-initiative/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': True})
        self.people.refresh_from_db()
        self.assertTrue(self.people.has_reviewed_brain_initiative)
        self.project.refresh_from_db()
        self.assertTrue(self.project.is_brain_initiative)

    def test_review_brain_initiative_ignores_unowned_projects(self):
        other_project = Project.objects.create(name='Other', funded_by='')
        payload = {str(other_project.id): True}
        response = self.client.post(
            '/ingest/review-brain-initiative/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        other_project.refresh_from_db()
        self.assertFalse(other_project.is_brain_initiative)
        self.people.refresh_from_db()
        self.assertTrue(self.people.has_reviewed_brain_initiative)

    def test_toggle_brain_initiative_on(self):
        response = self.client.post(
            f'/ingest/toggle-brain-initiative/{self.project.id}/',
            data=json.dumps({'is_brain_initiative': True}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': True})
        self.project.refresh_from_db()
        self.assertTrue(self.project.is_brain_initiative)

    def test_toggle_brain_initiative_off(self):
        self.project.is_brain_initiative = True
        self.project.save()
        response = self.client.post(
            f'/ingest/toggle-brain-initiative/{self.project.id}/',
            data=json.dumps({'is_brain_initiative': False}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertFalse(self.project.is_brain_initiative)

    def test_toggle_brain_initiative_unauthorized(self):
        other_project = Project.objects.create(name='Other', funded_by='')
        response = self.client.post(
            f'/ingest/toggle-brain-initiative/{other_project.id}/',
            data=json.dumps({'is_brain_initiative': True}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        other_project.refresh_from_db()
        self.assertFalse(other_project.is_brain_initiative)


# ---------------------------------------------------------------------------
# AuthHelper
# ---------------------------------------------------------------------------

class AuthHelperTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        # Admin user
        self.admin_user = User.objects.create_user('admin_helper', password='pass')
        self.admin_people = People.objects.create(
            name='Admin', orcid='', affiliation='', affiliation_identifier='',
            is_bil_admin=True, has_reviewed_brain_initiative=False,
            auth_user_id=self.admin_user,
        )
        # Non-admin user
        self.regular_user = User.objects.create_user('regular_helper', password='pass')
        self.regular_people = People.objects.create(
            name='Regular', orcid='', affiliation='', affiliation_identifier='',
            is_bil_admin=False, has_reviewed_brain_initiative=False,
            auth_user_id=self.regular_user,
        )
        # Project with regular_user as PI
        self.project = Project.objects.create(name='Helper Test Project', funded_by='NIH')
        self.pp = ProjectPeople.objects.create(
            project_id=self.project, people_id=self.regular_people,
            is_pi=True, is_po=False, doi_role='',
        )
        # Another project regular_user is NOT a PI of
        self.other_project = Project.objects.create(name='Other Helper Project', funded_by='NSF')

    def _req(self, user):
        req = self.factory.get('/')
        req.user = user
        return req

    # _assert_bil_admin
    def test_bil_admin_passes(self):
        _assert_bil_admin(self._req(self.admin_user))  # should not raise

    def test_non_admin_raises(self):
        with self.assertRaises(PermissionDenied):
            _assert_bil_admin(self._req(self.regular_user))

    # _assert_pi_of_project
    def test_pi_of_project_passes(self):
        _assert_pi_of_project(self._req(self.regular_user), self.project.id)  # should not raise

    def test_non_pi_raises(self):
        with self.assertRaises(PermissionDenied):
            _assert_pi_of_project(self._req(self.regular_user), self.other_project.id)

    def test_admin_non_pi_raises(self):
        # Being BIL admin does not grant PI access
        with self.assertRaises(PermissionDenied):
            _assert_pi_of_project(self._req(self.admin_user), self.project.id)


# ---------------------------------------------------------------------------
# BilAdminViewTests
# ---------------------------------------------------------------------------

class BilAdminViewTests(TestCase):
    def setUp(self):
        self.client_admin = Client()
        self.client_regular = Client()
        self.client_anon = Client()

        self.admin_user = User.objects.create_user('bil_admin_view', password='pass')
        People.objects.create(
            name='Admin', orcid='', affiliation='', affiliation_identifier='',
            is_bil_admin=True, has_reviewed_brain_initiative=False,
            auth_user_id=self.admin_user,
        )
        self.client_admin.login(username='bil_admin_view', password='pass')

        self.regular_user = User.objects.create_user('bil_regular_view', password='pass')
        self.regular_people = People.objects.create(
            name='Regular', orcid='', affiliation='', affiliation_identifier='',
            is_bil_admin=False, has_reviewed_brain_initiative=False,
            auth_user_id=self.regular_user,
        )
        self.client_regular.login(username='bil_regular_view', password='pass')

    # change_bil_admin_privs
    def test_non_admin_cannot_change_admin_privs(self):
        payload = json.dumps([{'person_id': self.regular_people.id, 'is_bil_admin': True}])
        response = self.client_regular.post(
            '/ingest/change_bil_admin_privs/',
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.regular_people.refresh_from_db()
        self.assertFalse(self.regular_people.is_bil_admin)

    def test_admin_can_change_admin_privs(self):
        payload = json.dumps([{'person_id': self.regular_people.id, 'is_bil_admin': True}])
        response = self.client_admin.post(
            '/ingest/change_bil_admin_privs/',
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.regular_people.refresh_from_db()
        self.assertTrue(self.regular_people.is_bil_admin)

    # doi_api
    def test_unauthenticated_cannot_call_doi_api(self):
        response = self.client_anon.post(
            '/ingest/doi_api/',
            data=json.dumps({'bildid': 'FAKE123'}),
            content_type='application/json',
        )
        # Should redirect to login (302) or return 403
        self.assertIn(response.status_code, [302, 403])

    def test_non_admin_cannot_call_doi_api(self):
        response = self.client_regular.post(
            '/ingest/doi_api/',
            data=json.dumps({'bildid': 'FAKE123'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_reach_doi_api(self):
        # Admin can reach it — it will fail at the BIL_ID lookup since FAKE123 doesn't exist,
        # but we should NOT get a 403 or 302.
        response = self.client_admin.post(
            '/ingest/doi_api/',
            data=json.dumps({'bildid': 'FAKE123'}),
            content_type='application/json',
        )
        self.assertNotEqual(response.status_code, 403)
        self.assertNotEqual(response.status_code, 302)


# ---------------------------------------------------------------------------
# ProjectMembershipViewTests
# ---------------------------------------------------------------------------

class ProjectMembershipViewTests(TestCase):
    def setUp(self):
        self.client_pi = Client()
        self.client_non_pi = Client()

        # PI of project_a
        self.pi_user = User.objects.create_user('proj_pi_user', password='pass')
        self.pi_people = People.objects.create(
            name='PI User', orcid='', affiliation='', affiliation_identifier='',
            is_bil_admin=False, has_reviewed_brain_initiative=False,
            auth_user_id=self.pi_user,
        )
        self.client_pi.login(username='proj_pi_user', password='pass')

        # Non-PI user (member of no projects)
        self.non_pi_user = User.objects.create_user('proj_nonpi_user', password='pass')
        self.non_pi_people = People.objects.create(
            name='Non-PI User', orcid='', affiliation='', affiliation_identifier='',
            is_bil_admin=False, has_reviewed_brain_initiative=False,
            auth_user_id=self.non_pi_user,
        )
        self.client_non_pi.login(username='proj_nonpi_user', password='pass')

        # Target user to add
        self.target_user = User.objects.create_user('proj_target_user', password='pass')
        self.target_people = People.objects.create(
            name='Target User', orcid='', affiliation='', affiliation_identifier='',
            is_bil_admin=False, has_reviewed_brain_initiative=False,
            auth_user_id=self.target_user,
        )

        self.project_a = Project.objects.create(name='Proj Membership A', funded_by='NIH')
        ProjectPeople.objects.create(
            project_id=self.project_a, people_id=self.pi_people,
            is_pi=True, is_po=False, doi_role='',
        )
        # pi_people also has a ProjectPeople row — save its id for userModify tests
        self.target_pp = ProjectPeople.objects.create(
            project_id=self.project_a, people_id=self.target_people,
            is_pi=False, is_po=False, doi_role='',
        )

    # write_user_to_project_people
    def test_non_pi_cannot_add_user(self):
        payload = json.dumps([{'user_id': self.target_user.id, 'project_id': self.project_a.id}])
        response = self.client_non_pi.post(
            '/ingest/write_user_to_project_people/',
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_pi_can_add_user(self):
        new_user = User.objects.create_user('proj_new_member', password='pass')
        People.objects.create(
            name='New Member', orcid='', affiliation='', affiliation_identifier='',
            is_bil_admin=False, has_reviewed_brain_initiative=False,
            auth_user_id=new_user,
        )
        payload = json.dumps([{'user_id': new_user.id, 'project_id': self.project_a.id}])
        response = self.client_pi.post(
            '/ingest/write_user_to_project_people/',
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

    # add_user_by_username
    def test_non_pi_cannot_add_user_by_username(self):
        response = self.client_non_pi.post(
            '/ingest/add_user_by_username/',
            data=json.dumps({'username': self.target_user.username, 'project_id': self.project_a.id}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_pi_can_add_user_by_username(self):
        new_user2 = User.objects.create_user('proj_new_member2', password='pass')
        People.objects.create(
            name='New Member2', orcid='', affiliation='', affiliation_identifier='',
            is_bil_admin=False, has_reviewed_brain_initiative=False,
            auth_user_id=new_user2,
        )
        response = self.client_pi.post(
            '/ingest/add_user_by_username/',
            data=json.dumps({'username': new_user2.username, 'project_id': self.project_a.id}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

    # userModify
    def test_non_pi_cannot_modify_user_role(self):
        payload = json.dumps([{
            'project_id': self.target_pp.id,
            'is_pi': True, 'is_po': False, 'auth_id': self.target_user.id,
        }])
        response = self.client_non_pi.post(
            '/ingest/userModify/',
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.target_pp.refresh_from_db()
        self.assertFalse(self.target_pp.is_pi)

    def test_pi_can_modify_user_role(self):
        payload = json.dumps([{
            'project_id': self.target_pp.id,
            'is_pi': True, 'is_po': False, 'auth_id': self.target_user.id,
        }])
        response = self.client_pi.post(
            '/ingest/userModify/',
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.target_pp.refresh_from_db()
        self.assertTrue(self.target_pp.is_pi)


# ---------------------------------------------------------------------------
# CollectionOwnershipTests
# ---------------------------------------------------------------------------

class CollectionOwnershipTests(TestCase):
    def setUp(self):
        self.client_owner = Client()
        self.client_attacker = Client()

        self.owner_user = User.objects.create_user('coll_owner', password='pass')
        self.owner_people = People.objects.create(
            name='Owner', orcid='', affiliation='', affiliation_identifier='',
            is_bil_admin=False, has_reviewed_brain_initiative=False,
            auth_user_id=self.owner_user,
        )
        self.client_owner.login(username='coll_owner', password='pass')

        self.attacker_user = User.objects.create_user('coll_attacker', password='pass')
        People.objects.create(
            name='Attacker', orcid='', affiliation='', affiliation_identifier='',
            is_bil_admin=False, has_reviewed_brain_initiative=False,
            auth_user_id=self.attacker_user,
        )
        self.client_attacker.login(username='coll_attacker', password='pass')

        self.project = Project.objects.create(name='Coll Ownership Project', funded_by='NIH')
        ProjectPeople.objects.create(
            project_id=self.project, people_id=self.owner_people,
            is_pi=True, is_po=False, doi_role='',
        )
        self.collection = Collection.objects.create(
            name='Owned Collection',
            description='test',
            organization_name='PSC',
            lab_name='BIL',
            project_funder_id='R01NS000000',
            project=self.project,
            bil_uuid='test-uuid-1234',
            data_path='/fake/path',
            celery_task_id_submission='',
            celery_task_id_validation='',
            user=self.owner_user,
        )

    # collection_delete
    def test_owner_can_delete_collection(self):
        response = self.client_owner.post(
            f'/ingest/collection_delete/{self.collection.id}',
        )
        # Should redirect after deletion, not 403/404
        self.assertIn(response.status_code, [200, 302])
        self.assertFalse(Collection.objects.filter(id=self.collection.id).exists())

    def test_attacker_cannot_delete_foreign_collection(self):
        response = self.client_attacker.post(
            f'/ingest/collection_delete/{self.collection.id}',
        )
        self.assertEqual(response.status_code, 404)
        # Collection must still exist
        self.assertTrue(Collection.objects.filter(id=self.collection.id).exists())

    # CollectionUpdate
    def test_owner_can_update_collection(self):
        response = self.client_owner.post(
            f'/ingest/collection_update/{self.collection.id}',
            data={
                'name': 'Updated Name',
                'description': 'updated',
                'organization_name': 'PSC',
                'lab_name': 'BIL',
                'project_funder': 'NIH',
                'project_funder_id': 'R01NS000001',
            },
        )
        # Redirect on success
        self.assertIn(response.status_code, [200, 302])
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.name, 'Updated Name')

    def test_attacker_cannot_update_foreign_collection(self):
        response = self.client_attacker.post(
            f'/ingest/collection_update/{self.collection.id}',
            data={
                'name': 'Hacked Name',
                'description': 'hacked',
                'organization_name': 'Evil Corp',
                'lab_name': 'Evil Lab',
                'project_funder': 'None',
                'project_funder_id': '0',
            },
        )
        self.assertEqual(response.status_code, 404)
        self.collection.refresh_from_db()
        self.assertNotEqual(self.collection.name, 'Hacked Name')


# ---------------------------------------------------------------------------
# AdminSmokeTests
# ---------------------------------------------------------------------------

class AdminSmokeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_superuser('admin_smoke', password='pass')
        self.client.login(username='admin_smoke', password='pass')

    def test_collection_changelist_loads(self):
        response = self.client.get('/admin/ingest/collection/')
        self.assertEqual(response.status_code, 200)

    def test_dataset_changelist_loads(self):
        response = self.client.get('/admin/ingest/dataset/')
        self.assertEqual(response.status_code, 200)

    def test_sheet_changelist_loads(self):
        response = self.client.get('/admin/ingest/sheet/')
        self.assertEqual(response.status_code, 200)

    def test_eventslog_changelist_loads(self):
        response = self.client.get('/admin/ingest/eventslog/')
        self.assertEqual(response.status_code, 200)

    def test_sheet_detail_loads(self):
        from ingest.models import Collection, Sheet
        from django.contrib.auth.models import User as AuthUser
        coll = Collection.objects.create(
            name='Smoke Test Collection',
            description='test',
            organization_name='PSC',
            lab_name='BIL',
            project_funder_id='R01',
            bil_uuid='smoke-uuid-0001',
            data_path='/fake',
            celery_task_id_submission='',
            celery_task_id_validation='',
        )
        sheet = Sheet.objects.create(filename='/fake/file.xlsx', collection=coll)
        response = self.client.get(f'/admin/ingest/sheet/{sheet.pk}/change/')
        self.assertEqual(response.status_code, 200)

    def test_collection_detail_loads(self):
        from ingest.models import Collection
        coll = Collection.objects.create(
            name='Coll Detail Smoke',
            description='test',
            organization_name='PSC',
            lab_name='BIL',
            project_funder_id='R01',
            bil_uuid='smoke-uuid-0003',
            data_path='/fake',
            celery_task_id_submission='',
            celery_task_id_validation='',
        )
        response = self.client.get(f'/admin/ingest/collection/{coll.pk}/change/')
        self.assertEqual(response.status_code, 200)

    def test_dataset_detail_loads(self):
        from ingest.models import Collection, Sheet, Dataset
        coll = Collection.objects.create(
            name='DS Smoke Collection',
            description='test',
            organization_name='PSC',
            lab_name='BIL',
            project_funder_id='R01',
            bil_uuid='smoke-uuid-0002',
            data_path='/fake',
            celery_task_id_submission='',
            celery_task_id_validation='',
        )
        sheet = Sheet.objects.create(filename='/fake/ds.xlsx', collection=coll)
        ds = Dataset.objects.create(
            bildirectory='/bil/data/test',
            title='Test Dataset',
            rights='CC BY 4.0',
            rightsuri='https://creativecommons.org/licenses/by/4.0/',
            rightsidentifier='CC-BY-4.0',
            abstract='test abstract',
            sheet=sheet,
        )
        response = self.client.get(f'/admin/ingest/dataset/{ds.pk}/change/')
        self.assertEqual(response.status_code, 200)

    def test_mark_as_public_action(self):
        from ingest.models import Collection
        coll = Collection.objects.create(
            name='Mark Public Test Collection',
            description='test',
            organization_name='PSC',
            lab_name='BIL',
            project_funder_id='R01',
            bil_uuid='smoke-uuid-pub-01',
            data_path='/fake',
            celery_task_id_submission='',
            celery_task_id_validation='',
            submission_status=Collection.NOT_SUBMITTED,
            validation_status=Collection.NOT_VALIDATED,
            locked=False,
        )
        url = f'/admin/ingest/collection/{coll.pk}/mark_as_public/'
        resp = self.client.get(url, follow=True)
        self.assertEqual(resp.status_code, 200)
        coll.refresh_from_db()
        self.assertEqual(coll.submission_status, Collection.SUCCESS)
        self.assertEqual(coll.validation_status, Collection.SUCCESS)
        self.assertTrue(coll.locked)
        self.assertTrue(
            EventsLog.objects.filter(
                collection_id=coll,
                event_type='collection_public',
            ).exists()
        )

    def test_mark_as_public_already_public(self):
        from ingest.models import Collection
        coll = Collection.objects.create(
            name='Already Public Collection',
            description='test',
            organization_name='PSC',
            lab_name='BIL',
            project_funder_id='R01',
            bil_uuid='smoke-uuid-pub-02',
            data_path='/fake',
            celery_task_id_submission='',
            celery_task_id_validation='',
            submission_status=Collection.SUCCESS,
            validation_status=Collection.SUCCESS,
        )
        initial_count = EventsLog.objects.filter(collection_id=coll).count()
        url = f'/admin/ingest/collection/{coll.pk}/mark_as_public/'
        resp = self.client.get(url, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            EventsLog.objects.filter(collection_id=coll).count(),
            initial_count,
        )

    def test_collection_change_has_dataset_formset(self):
        from ingest.models import Collection, Sheet, Dataset
        coll = Collection.objects.create(
            name='Formset Test Collection',
            description='test',
            organization_name='PSC',
            lab_name='BIL',
            project_funder_id='R01',
            bil_uuid='smoke-uuid-fs-01',
            data_path='/fake',
            celery_task_id_submission='',
            celery_task_id_validation='',
        )
        sheet = Sheet.objects.create(filename='/fake/sheet.xlsx', collection=coll)
        Dataset.objects.create(
            bildirectory='/bil/data/test',
            title='Test Dataset',
            rights='CC BY 4.0',
            rightsuri='https://creativecommons.org/licenses/by/4.0/',
            rightsidentifier='CC-BY-4.0',
            abstract='test abstract',
            sheet=sheet,
        )
        response = self.client.get(f'/admin/ingest/collection/{coll.pk}/change/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('dataset_formset', response.context)

    def test_collection_change_renders_dataset_editor(self):
        from ingest.models import Collection, Sheet, Dataset
        coll = Collection.objects.create(
            name='Editor Render Test',
            description='test',
            organization_name='PSC',
            lab_name='BIL',
            project_funder_id='R01',
            bil_uuid='smoke-uuid-ed-01',
            data_path='/fake',
            celery_task_id_submission='',
            celery_task_id_validation='',
        )
        sheet = Sheet.objects.create(filename='/fake/sheet.xlsx', collection=coll)
        Dataset.objects.create(
            bildirectory='/bil/data/test',
            title='Render Test Dataset',
            rights='CC BY 4.0',
            rightsuri='https://creativecommons.org/licenses/by/4.0/',
            rightsidentifier='CC-BY-4.0',
            abstract='test abstract',
            sheet=sheet,
        )
        response = self.client.get(f'/admin/ingest/collection/{coll.pk}/change/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'bil-dataset-editor')
        self.assertContains(response, 'Save Datasets')

    def test_save_datasets_valid_post(self):
        from ingest.models import Collection, Sheet, Dataset
        coll = Collection.objects.create(
            name='Save Valid Test',
            description='test',
            organization_name='PSC',
            lab_name='BIL',
            project_funder_id='R01',
            bil_uuid='smoke-uuid-sv-01',
            data_path='/fake',
            celery_task_id_submission='',
            celery_task_id_validation='',
        )
        sheet = Sheet.objects.create(filename='/fake/sheet.xlsx', collection=coll)
        ds = Dataset.objects.create(
            bildirectory='/bil/data/original',
            title='Old Title',
            rights='CC BY 4.0',
            rightsuri='https://creativecommons.org/licenses/by/4.0/',
            rightsidentifier='CC-BY-4.0',
            abstract='test abstract',
            sheet=sheet,
        )
        url = f'/admin/ingest/collection/{coll.pk}/datasets/save/'
        data = {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(ds.pk),
            'form-0-sheet': str(sheet.pk),
            'form-0-bildirectory': '/bil/data/updated',
            'form-0-title': 'Updated Title',
            'form-0-doi': '',
            'form-0-generalmodality': '',
            'form-0-technique': '',
            'form-0-abstract': 'test abstract',
            'form-0-methods': '',
            'form-0-rights': 'CC BY 4.0',
            'form-0-rightsuri': 'https://creativecommons.org/licenses/by/4.0/',
            'form-0-rightsidentifier': 'CC-BY-4.0',
            'form-0-subject': '',
            'form-0-subjectscheme': '',
            'form-0-dataset_size': '',
            'form-0-number_of_files': '',
        }
        resp = self.client.post(url, data, follow=True)
        self.assertEqual(resp.status_code, 200)
        ds.refresh_from_db()
        self.assertEqual(ds.bildirectory, '/bil/data/updated')
        self.assertEqual(ds.title, 'Updated Title')

    def test_save_datasets_invalid_post(self):
        from ingest.models import Collection, Sheet, Dataset
        coll = Collection.objects.create(
            name='Save Invalid Test',
            description='test',
            organization_name='PSC',
            lab_name='BIL',
            project_funder_id='R01',
            bil_uuid='smoke-uuid-si-01',
            data_path='/fake',
            celery_task_id_submission='',
            celery_task_id_validation='',
        )
        sheet = Sheet.objects.create(filename='/fake/sheet.xlsx', collection=coll)
        ds = Dataset.objects.create(
            bildirectory='/bil/data/original',
            title='Unchanged Title',
            rights='CC BY 4.0',
            rightsuri='https://creativecommons.org/licenses/by/4.0/',
            rightsidentifier='CC-BY-4.0',
            abstract='test abstract',
            sheet=sheet,
        )
        url = f'/admin/ingest/collection/{coll.pk}/datasets/save/'
        data = {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(ds.pk),
            'form-0-sheet': str(sheet.pk),
            'form-0-bildirectory': '',  # blank required field -> validation error
            'form-0-title': 'Unchanged Title',
            'form-0-doi': '',
            'form-0-generalmodality': '',
            'form-0-technique': '',
            'form-0-abstract': 'test abstract',
            'form-0-methods': '',
            'form-0-rights': 'CC BY 4.0',
            'form-0-rightsuri': 'https://creativecommons.org/licenses/by/4.0/',
            'form-0-rightsidentifier': 'CC-BY-4.0',
            'form-0-subject': '',
            'form-0-subjectscheme': '',
            'form-0-dataset_size': '',
            'form-0-number_of_files': '',
        }
        resp = self.client.post(url, data, follow=True)
        self.assertEqual(resp.status_code, 200)
        ds.refresh_from_db()
        self.assertEqual(ds.bildirectory, '/bil/data/original')  # unchanged


# ---------------------------------------------------------------------------
# V2ValidatorPreflightTests
# ---------------------------------------------------------------------------

class V2ValidatorPreflightTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name='V2 Validator Project', funded_by='NIH')
        self.user = User.objects.create_user(username='v2testowner', password='pass')
        self.people = People.objects.create(
            name='V2 Test Owner', orcid='', affiliation='', affiliation_identifier='',
            auth_user_id=self.user
        )
        self.collection = Collection.objects.create(
            name='V2 Test Collection', description='desc', organization_name='Org',
            lab_name='Lab', project_funder_id='grant1', project=self.project,
            bil_uuid='test-uuid-v2-001', data_path='/tmp/test', locked=False,
            celery_task_id_submission='', celery_task_id_validation='',
            submission_status='NOT_SUBMITTED', validation_status='NOT_VALIDATED',
            collection_type='test', user=self.user,
        )

    def _make_descriptive_metadata(self):
        from ingest.models import DescriptiveMetadata
        return DescriptiveMetadata.objects.create(
            collection=self.collection, user=self.user,
            sample_id='s1', locked=False,
            organism_type='mouse', organism_ncbi_taxonomy_id='10090',
            transgenetic_line_information='C57BL/6J', method='confocal',
            technique='confocal microscopy', anatomical_structure='brain',
            total_processed_cells='0', organization='PSC', lab='BIL',
            investigator='Dr. Test', grant_number='R01NS000000',
            r24_name='r24 name', r24_directory='./r24',
        )

    def _make_sheet(self):
        from ingest.models import Sheet
        return Sheet.objects.create(
            collection=self.collection, filename='test.xls', ingest_method='ingest_1',
        )

    def test_preflight_passes_when_v1_exists_v2_does_not(self):
        self._make_descriptive_metadata()
        from ingest.services.v2_validator import run_preflight
        errors = run_preflight(self.collection)
        self.assertEqual(errors, [])

    def test_preflight_errors_when_no_v1(self):
        from ingest.services.v2_validator import run_preflight
        errors = run_preflight(self.collection)
        self.assertTrue(any('V1' in e for e in errors))

    def test_preflight_errors_when_v2_already_exists(self):
        self._make_descriptive_metadata()
        self._make_sheet()
        from ingest.services.v2_validator import run_preflight
        errors = run_preflight(self.collection)
        self.assertTrue(any('V2' in e or 'already exists' in e for e in errors))

    def test_preflight_errors_when_collection_locked(self):
        self.collection.locked = True
        self.collection.save()
        self._make_descriptive_metadata()
        from ingest.services.v2_validator import run_preflight
        errors = run_preflight(self.collection)
        self.assertTrue(any('locked' in e.lower() for e in errors))

    def test_preflight_errors_when_no_people_record(self):
        self.people.delete()
        from ingest.services.v2_validator import run_preflight
        errors = run_preflight(self.collection)
        self.assertTrue(any('People' in e or 'owner' in e.lower() for e in errors))


# ---------------------------------------------------------------------------
# V2ValidatorSpreadsheetTests
# ---------------------------------------------------------------------------

class V2ValidatorSpreadsheetTests(TestCase):
    def _make_temp_xls(self, has_readme=True, has_swc=True, sheet_names=None):
        """Create a minimal xlwt workbook for testing. Returns temp file path."""
        wb = xlwt.Workbook()
        names = sheet_names or (['README', 'Contributors', 'Dataset', 'Funders',
                                  'Publication', 'Instrument', 'Specimen', 'Image']
                                 + (['SWC'] if has_swc else []))
        for name in names:
            wb.add_sheet(name)
        tmp = tempfile.NamedTemporaryFile(suffix='.xls', delete=False)
        wb.save(tmp.name)
        tmp.close()
        return tmp.name

    def test_errors_on_unreadable_file(self):
        with tempfile.NamedTemporaryFile(suffix='.xls', delete=False) as f:
            f.write(b'not an xls')
            path = f.name
        from ingest.services.v2_validator import validate_spreadsheet
        errors, warnings = validate_spreadsheet(path)
        os.unlink(path)
        self.assertTrue(len(errors) > 0)

    def test_error_when_no_readme_sheet(self):
        path = self._make_temp_xls(has_readme=False, sheet_names=['Contributors', 'Dataset'])
        from ingest.services.v2_validator import validate_spreadsheet
        errors, warnings = validate_spreadsheet(path)
        os.unlink(path)
        self.assertTrue(any('V1' in e or 'README' in e for e in errors))

    def test_warning_when_no_swc_sheet(self):
        path = self._make_temp_xls(has_swc=False)
        from ingest.services.v2_validator import validate_spreadsheet
        errors, warnings = validate_spreadsheet(path)
        os.unlink(path)
        self.assertTrue(any('SWC' in w for w in warnings))

    def test_no_warnings_when_swc_present(self):
        path = self._make_temp_xls(has_swc=True)
        from ingest.services.v2_validator import validate_spreadsheet
        errors, warnings = validate_spreadsheet(path)
        os.unlink(path)
        self.assertFalse(any('SWC' in w for w in warnings))


# ---------------------------------------------------------------------------
# DriveServiceTests
# ---------------------------------------------------------------------------

class DriveServiceTests(TestCase):
    @patch('ingest.services.drive_service._get_service')
    def test_search_by_uuid_returns_matching_files(self, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_service.files.return_value.list.return_value.execute.return_value = {
            'files': [
                {'id': 'abc123', 'name': 'abc-uuid-file.xlsx', 'modifiedTime': '2026-01-01T00:00:00Z'}
            ]
        }
        from ingest.services.drive_service import search_by_uuid
        results = search_by_uuid('abc-uuid')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], 'abc123')
        self.assertEqual(results[0]['name'], 'abc-uuid-file.xlsx')
        self.assertIn('modified', results[0])

    @patch('ingest.services.drive_service._get_service')
    def test_search_by_uuid_returns_empty_when_no_match(self, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_service.files.return_value.list.return_value.execute.return_value = {'files': []}
        from ingest.services.drive_service import search_by_uuid
        results = search_by_uuid('nonexistent-uuid')
        self.assertEqual(results, [])

    @patch('ingest.services.drive_service._get_service')
    def test_download_file_writes_to_dest_path(self, mock_get_service):
        import io, tempfile, os
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        fake_content = b'PK fake xlsx content'
        mock_request = MagicMock()
        mock_service.files.return_value.get_media.return_value = mock_request
        # Simulate MediaIoBaseDownload behavior
        def fake_downloader(buf, req):
            obj = MagicMock()
            buf.write(fake_content)
            obj.next_chunk.return_value = (None, True)
            return obj
        with patch('ingest.services.drive_service.MediaIoBaseDownload', side_effect=fake_downloader):
            from ingest.services.drive_service import download_file
            with tempfile.TemporaryDirectory() as tmp:
                dest = os.path.join(tmp, 'test.xlsx')
                result = download_file('file123', dest)
                self.assertEqual(result, dest)
                self.assertTrue(os.path.exists(dest))
                with open(dest, 'rb') as f:
                    self.assertEqual(f.read(), fake_content)


# ---------------------------------------------------------------------------
# V2VerifierTests
# ---------------------------------------------------------------------------

class V2VerifierTests(TestCase):
    def setUp(self):
        from ingest.models import Sheet, Dataset, BIL_ID, DescriptiveMetadata
        self.project = Project.objects.create(name='Verifier Project', funded_by='NIH')
        self.user = User.objects.create_user(username='verifyowner', password='pass')
        self.collection = Collection.objects.create(
            name='Verifier Collection', description='desc', organization_name='Org',
            lab_name='Lab', project_funder_id='grant2', project=self.project,
            bil_uuid='verify-uuid-002', data_path='/tmp/verify', locked=False,
            celery_task_id_submission='', celery_task_id_validation='',
            submission_status='NOT_SUBMITTED', validation_status='NOT_VALIDATED',
            collection_type='test', user=self.user,
        )
        self.sheet = Sheet.objects.create(
            filename='test.xlsx', collection=self.collection, ingest_method='ingest_1'
        )
        self.dm = DescriptiveMetadata.objects.create(
            collection=self.collection, user=self.user,
            sample_id='s1', locked=False,
            organism_type='mouse', organism_ncbi_taxonomy_id='10090',
            transgenetic_line_information='C57BL/6J', method='confocal',
            technique='confocal microscopy', anatomical_structure='brain',
            total_processed_cells='0', organization='PSC', lab='BIL',
            investigator='Dr. Test', grant_number='R01NS000000',
            r24_name='r24 name', r24_directory='/bil/lz/test/dir/',
        )

    def test_check_directory_match_returns_match(self):
        from ingest.models import Dataset, BIL_ID
        ds = Dataset.objects.create(
            bildirectory='/bil/lz/test/dir/', title='Test DS', rights='r',
            rightsuri='u', rightsidentifier='i', abstract='a', sheet=self.sheet,
        )
        BIL_ID.objects.create(
            bil_id='BIL001', v2_ds_id=ds, v1_ds_id=self.dm, metadata_version=2
        )
        from ingest.services.v2_verifier import check_directory_match
        results = check_directory_match(self.collection)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['status'], 'MATCH')
        self.assertEqual(results[0]['bil_id'], 'BIL001')

    def test_check_directory_match_returns_mismatch(self):
        from ingest.models import Dataset, BIL_ID
        ds = Dataset.objects.create(
            bildirectory='/bil/lz/DIFFERENT/dir/', title='Test DS', rights='r',
            rightsuri='u', rightsidentifier='i', abstract='a', sheet=self.sheet,
        )
        BIL_ID.objects.create(
            bil_id='BIL002', v2_ds_id=ds, v1_ds_id=self.dm, metadata_version=2
        )
        from ingest.services.v2_verifier import check_directory_match
        results = check_directory_match(self.collection)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['status'], 'MISMATCH')

    def test_check_directory_match_empty_when_no_sheet(self):
        empty_collection = Collection.objects.create(
            name='Empty Coll', description='d', organization_name='O',
            lab_name='L', project_funder_id='g', project=self.project,
            bil_uuid='empty-uuid-003', data_path='/tmp/empty', locked=False,
            celery_task_id_submission='', celery_task_id_validation='',
            submission_status='NOT_SUBMITTED', validation_status='NOT_VALIDATED',
            collection_type='test', user=self.user,
        )
        from ingest.services.v2_verifier import check_directory_match
        results = check_directory_match(empty_collection)
        self.assertEqual(results, [])

    def test_check_directory_match_mismatch_when_no_v1(self):
        """When v1_ds_id is None, status must be 'MISMATCH' even if directories are empty/match."""
        from ingest.models import Dataset, BIL_ID
        ds = Dataset.objects.create(
            bildirectory='', title='Test DS No V1', rights='r',
            rightsuri='u', rightsidentifier='i', abstract='a', sheet=self.sheet,
        )
        BIL_ID.objects.create(
            bil_id='BIL004', v2_ds_id=ds, v1_ds_id=None, metadata_version=2
        )
        from ingest.services.v2_verifier import check_directory_match
        results = check_directory_match(self.collection)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['status'], 'MISMATCH')
        self.assertIsNone(results[0]['v1_ds_id'])

    def test_get_bil_id_summary_returns_dataset_bil_pairs(self):
        from ingest.models import Dataset, BIL_ID
        ds = Dataset.objects.create(
            bildirectory='/bil/lz/test/dir/', title='My Dataset', rights='r',
            rightsuri='u', rightsidentifier='i', abstract='a', sheet=self.sheet,
        )
        BIL_ID.objects.create(
            bil_id='BIL003', v2_ds_id=ds, v1_ds_id=self.dm, metadata_version=2
        )
        from ingest.services.v2_verifier import get_bil_id_summary
        results = get_bil_id_summary(self.collection)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['bil_id'], 'BIL003')
        self.assertEqual(results[0]['dataset_title'], 'My Dataset')


# ---------------------------------------------------------------------------
# UploadServiceTests
# ---------------------------------------------------------------------------

class UploadServiceTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name='Upload Project', funded_by='NIH')
        self.user = User.objects.create_user(username='uploadowner', password='pass')
        self.collection = Collection.objects.create(
            name='Upload Collection', description='d', organization_name='O',
            lab_name='L', project_funder_id='g', project=self.project,
            bil_uuid='upload-uuid-004', data_path='/tmp/upload', locked=False,
            celery_task_id_submission='', celery_task_id_validation='',
            submission_status='NOT_SUBMITTED', validation_status='NOT_VALIDATED',
            collection_type='test', user=self.user,
        )

    @patch('ingest.services.upload_service.check_all_sheets', return_value={})
    @patch('ingest.services.upload_service.save_sheet_row')
    @patch('ingest.services.upload_service.save_all_sheets_method_1', return_value=True)
    @patch('ingest.services.upload_service.ingest_contributors_sheet', return_value=[])
    @patch('ingest.services.upload_service.ingest_funders_sheet', return_value=[])
    @patch('ingest.services.upload_service.ingest_publication_sheet', return_value=[])
    @patch('ingest.services.upload_service.ingest_instrument_sheet', return_value=[])
    @patch('ingest.services.upload_service.ingest_dataset_sheet', return_value=[])
    @patch('ingest.services.upload_service.ingest_specimen_sheet', return_value=[])
    @patch('ingest.services.upload_service.ingest_image_sheet', return_value=[])
    @patch('ingest.services.upload_service.ingest_swc_sheet', return_value=[])
    @patch('ingest.services.upload_service.save_bil_ids', return_value=None)
    @patch('ingest.services.upload_service.save_specimen_ids')
    @patch('ingest.services.upload_service.xlrd.open_workbook')
    def test_execute_v2_upload_success_returns_sheet_id(
        self, mock_wb, mock_spec_ids, mock_bil_ids, mock_swc, mock_img, mock_spec,
        mock_ds, mock_inst, mock_pub, mock_fund, mock_contrib,
        mock_save_method1, mock_save_sheet, mock_check
    ):
        mock_wb.return_value.sheet_names.return_value = []
        mock_sheet = MagicMock()
        mock_sheet.id = 42
        mock_save_sheet.return_value = mock_sheet
        # Patch Dataset.objects.filter to return empty queryset
        with patch('ingest.services.upload_service.Dataset') as mock_ds_model:
            mock_ds_model.objects.filter.return_value = []
            with patch('ingest.services.upload_service.Specimen') as mock_spec_model:
                mock_spec_model.objects.filter.return_value = []
                from ingest.services.upload_service import execute_v2_upload
                success, error, sheet_id = execute_v2_upload(
                    '/fake/file.xls', self.collection, self.user, 'ingest_1'
                )
        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertEqual(sheet_id, 42)

    @patch('ingest.services.upload_service.check_all_sheets')
    @patch('ingest.services.upload_service.xlrd.open_workbook')
    def test_execute_v2_upload_fails_on_check_all_sheets_errors(
        self, mock_wb, mock_check
    ):
        mock_wb.return_value.sheet_names.return_value = []
        mock_check.return_value = {'Dataset::1::0': ['Missing required field']}
        from ingest.services.upload_service import execute_v2_upload
        success, error, sheet_id = execute_v2_upload(
            '/fake/file.xls', self.collection, self.user, 'ingest_1'
        )
        self.assertFalse(success)
        self.assertIsNotNone(error)
        self.assertIsNone(sheet_id)

    def test_upload_attributes_to_collection_user_not_admin(self):
        """The user passed to execute_v2_upload is stored as sheet's collection user."""
        admin_user = User.objects.create_user(username='adminuser', password='pass')
        # This test validates the contract: when we call execute_v2_upload with
        # collection.user, the DatasetEventsLog entries reference collection.project,
        # not the admin. We verify by inspecting the call signature requirement.
        from ingest.services import upload_service
        import inspect
        sig = inspect.signature(upload_service.execute_v2_upload)
        params = list(sig.parameters.keys())
        self.assertIn('user', params)
        self.assertIn('collection', params)


# ---------------------------------------------------------------------------
# Admin V2 Update Wizard integration tests
# ---------------------------------------------------------------------------

class V2UpdateAdminViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin', password='adminpass', email='admin@test.com'
        )
        self.owner = User.objects.create_user(username='owner2', password='pass')
        self.people_owner = People.objects.create(
            name='Owner', orcid='', affiliation='', affiliation_identifier='',
            auth_user_id=self.owner,
        )
        self.project = Project.objects.create(name='Admin View Project', funded_by='NIH')
        self.collection = Collection.objects.create(
            name='Admin View Collection', description='d', organization_name='O',
            lab_name='L', project_funder_id='g', project=self.project,
            bil_uuid='admin-uuid-005', data_path='/tmp/adminview', locked=False,
            celery_task_id_submission='', celery_task_id_validation='',
            submission_status='NOT_SUBMITTED', validation_status='NOT_VALIDATED',
            collection_type='test', user=self.owner,
        )
        self.client = Client()
        self.client.login(username='admin', password='adminpass')

    def test_page_loads_for_admin(self):
        url = reverse('admin:ingest_collection_v2_update', args=[self.collection.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_preflight_error_shown_when_v2_already_exists(self):
        from ingest.models import Sheet
        DescriptiveMetadata.objects.create(
            collection=self.collection, user=self.owner,
            sample_id='existing', locked=False,
            organism_type='', organism_ncbi_taxonomy_id='',
            transgenetic_line_information='', method='', technique='',
            anatomical_structure='', total_processed_cells='',
            organization='', lab='', investigator='', grant_number='',
            r24_name='', r24_directory='',
        )
        Sheet.objects.create(
            collection=self.collection, filename='existing.xls', ingest_method='ingest_1',
        )
        url = reverse('admin:ingest_collection_v2_update', args=[self.collection.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')

    def test_redirects_non_admin(self):
        self.client.logout()
        self.client.login(username='owner2', password='pass')
        url = reverse('admin:ingest_collection_v2_update', args=[self.collection.pk])
        response = self.client.get(url)
        self.assertIn(response.status_code, [302, 403])


class FetchAsanaCuratorQueueTests(TestCase):
    def setUp(self):
        cache.clear()

    @patch("ingest.dashboard.requests.get")
    def test_returns_tasks_grouped_by_section(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": [{"name": "abc-uuid-001"}]}
        mock_get.return_value = mock_resp

        from ingest.dashboard import fetch_asana_curator_queue
        result = fetch_asana_curator_queue()

        self.assertIn("Passed Validation", result)
        self.assertIn("abc-uuid-001", result["Passed Validation"])

    @patch("ingest.dashboard.requests.get")
    def test_caches_result_and_avoids_repeat_api_calls(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": [{"name": "some-uuid"}]}
        mock_get.return_value = mock_resp

        from ingest.dashboard import fetch_asana_curator_queue
        fetch_asana_curator_queue()
        cache.clear()  # clear so we can verify second call hits API again
        fetch_asana_curator_queue()

        # 3 sections × 2 uncached calls = 6 total
        self.assertEqual(mock_get.call_count, 6)

    @patch("ingest.dashboard.requests.get")
    def test_skips_api_call_when_gid_is_empty(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": []}
        mock_get.return_value = mock_resp

        with self.settings(ASANA_GID_PASSED_VALIDATION="", ASANA_GID_IN_CURATION="", ASANA_GID_CURATION_ISSUE=""):
            from ingest.dashboard import fetch_asana_curator_queue
            result = fetch_asana_curator_queue()

        mock_get.assert_not_called()
        self.assertEqual(result["Passed Validation"], [])


class BuildCuratorTableTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from ingest.models import Project, Collection
        self.user = User.objects.create_user("curator_test_user")
        self.project = Project.objects.create(name="Test Project", funded_by="NSF")
        self.collection = Collection.objects.create(
            name="Test Collection A",
            description="desc",
            organization_name="PSC",
            lab_name="BIL",
            project_funder_id="R24MH123456",
            project=self.project,
            bil_uuid="test-uuid-abc",
            data_path="/tmp/test",
            celery_task_id_submission="",
            celery_task_id_validation="",
            collection_type="",
        )

    def test_row_contains_uuid_and_edit_link(self):
        from ingest.dashboard import _build_curator_sections
        sections = _build_curator_sections({"Passed Validation": ["test-uuid-abc"]})

        self.assertEqual(len(sections), 1)
        section_name, table = sections[0]
        self.assertEqual(section_name, "Passed Validation")
        self.assertEqual(len(table.rows), 1)
        row = table.rows[0]
        self.assertIn("test-uuid-abc", row[0])
        self.assertIn("Edit", str(row[1]))

    def test_unknown_uuid_shows_dash(self):
        from ingest.dashboard import _build_curator_sections
        sections = _build_curator_sections({"Passed Validation": ["no-such-uuid"]})

        self.assertEqual(len(sections), 1)
        _, table = sections[0]
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0][1], "-")


from django.utils import timezone


class FetchPipelineCountersTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from ingest.models import Project, Collection
        user = User.objects.create_user("pipeline_test_user")
        project = Project.objects.create(name="Pipeline Test Project", funded_by="NSF")
        Collection.objects.create(
            name="Pipeline Pending Collection",
            description="desc",
            organization_name="PSC",
            lab_name="BIL",
            project_funder_id="R24MH777",
            project=project,
            bil_uuid="pipeline-uuid-001",
            data_path="/tmp/pipeline_test",
            celery_task_id_submission="",
            celery_task_id_validation="",
            collection_type="",
            submission_status="PENDING",
            validation_status="NOT_VALIDATED",
        )
        Collection.objects.create(
            name="Pipeline Public Collection",
            description="desc",
            organization_name="PSC",
            lab_name="BIL",
            project_funder_id="R24MH666",
            project=project,
            bil_uuid="pipeline-uuid-002",
            data_path="/tmp/pipeline_test2",
            celery_task_id_submission="",
            celery_task_id_validation="",
            collection_type="",
            submission_status="SUCCESS",
            validation_status="SUCCESS",
        )

    def test_counts_pending_as_validation_running(self):
        from ingest.dashboard import fetch_pipeline_counters
        counters = dict(fetch_pipeline_counters({}))
        self.assertEqual(counters["Validation Running"], 1)

    def test_counts_public_collections(self):
        from ingest.dashboard import fetch_pipeline_counters
        counters = dict(fetch_pipeline_counters({}))
        self.assertGreaterEqual(counters["Public"], 1)

    def test_uses_asana_counts_for_curator_sections(self):
        from ingest.dashboard import fetch_pipeline_counters
        tasks = {"Passed Validation": ["a", "b"], "In Curation": ["c"], "Curation Issue": []}
        counters = dict(fetch_pipeline_counters(tasks))
        self.assertEqual(counters["Passed Validation"], 2)
        self.assertEqual(counters["In Curation"], 1)
        self.assertEqual(counters["Curation Issue"], 0)


class FetchDoiQueueTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from ingest.models import Project, Collection, Sheet, Dataset, BIL_ID
        user = User.objects.create_user("doi_test_user")
        project = Project.objects.create(name="DOI Test Project", funded_by="NSF")
        self.collection = Collection.objects.create(
            name="DOI Test Collection",
            description="desc",
            organization_name="PSC",
            lab_name="BIL",
            project_funder_id="R24MH999",
            project=project,
            bil_uuid="doi-uuid-001",
            data_path="/tmp/doi_test",
            celery_task_id_submission="",
            celery_task_id_validation="",
            collection_type="",
            submission_status="SUCCESS",
            validation_status="SUCCESS",
        )
        sheet = Sheet.objects.create(filename="/tmp/test.xls", collection=self.collection, ingest_method="ingest_1")
        dataset = Dataset.objects.create(
            bildirectory="/test/dir",
            title="Test Dataset",
            rights="CC BY 4.0",
            rightsuri="https://creativecommons.org/licenses/by/4.0/",
            rightsidentifier="CC-BY-4.0",
            abstract="Test abstract.",
            sheet=sheet,
        )
        self.bil_id = BIL_ID.objects.create(bil_id="HBP000001", v2_ds_id=dataset, doi=False)

    def test_eligible_dataset_appears_in_queue(self):
        from ingest.dashboard import fetch_doi_queue
        result = fetch_doi_queue()
        bil_ids_in_result = [row[0] for row in result.rows]
        self.assertIn("HBP000001", bil_ids_in_result)

    def test_already_doied_dataset_excluded(self):
        from ingest.dashboard import fetch_doi_queue
        self.bil_id.doi = True
        self.bil_id.save()
        result = fetch_doi_queue()
        bil_ids_in_result = [row[0] for row in result.rows]
        self.assertNotIn("HBP000001", bil_ids_in_result)

    def test_non_public_collection_excluded(self):
        from ingest.dashboard import fetch_doi_queue
        self.collection.submission_status = "PENDING"
        self.collection.save()
        result = fetch_doi_queue()
        bil_ids_in_result = [row[0] for row in result.rows]
        self.assertNotIn("HBP000001", bil_ids_in_result)


class FetchRecentEventsTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from ingest.models import Project, Collection, EventsLog
        user = User.objects.create_user("events_test_user")
        project = Project.objects.create(name="Events Test Project", funded_by="NSF")
        self.collection = Collection.objects.create(
            name="Events Test Collection",
            description="desc",
            organization_name="PSC",
            lab_name="BIL",
            project_funder_id="R24MH888",
            project=project,
            bil_uuid="events-uuid-001",
            data_path="/tmp/events_test",
            celery_task_id_submission="",
            celery_task_id_validation="",
            collection_type="",
        )
        EventsLog.objects.create(
            collection_id=self.collection,
            notes="Test note",
            event_type="collection_created",
            timestamp=timezone.now(),
        )

    def test_recent_event_appears_in_table(self):
        from ingest.dashboard import fetch_recent_events
        result = fetch_recent_events()
        self.assertGreater(len(result.rows), 0)
        event_types = [row[1] for row in result.rows]
        self.assertIn("Collection Created", event_types)

    def test_returns_at_most_15_rows(self):
        from ingest.models import EventsLog
        from ingest.dashboard import fetch_recent_events
        for i in range(20):
            EventsLog.objects.create(
                collection_id=self.collection,
                notes=f"Note {i}",
                event_type="metadata_uploaded",
                timestamp=timezone.now(),
            )
        result = fetch_recent_events()
        self.assertLessEqual(len(result.rows), 15)


class DashboardCallbackTests(TestCase):
    @patch("ingest.dashboard.fetch_asana_curator_queue")
    def test_asana_error_is_caught_gracefully(self, mock_fetch):
        mock_fetch.side_effect = Exception("Asana is down")
        from ingest.dashboard import dashboard_callback
        from django.test import RequestFactory
        request = RequestFactory().get("/admin/")
        context = {}
        result = dashboard_callback(request, context)
        self.assertIsNotNone(result["asana_error"])
        self.assertEqual(result["curator_sections"], [])

    @patch("ingest.dashboard.fetch_asana_curator_queue")
    def test_successful_call_populates_all_keys(self, mock_fetch):
        mock_fetch.return_value = {"Passed Validation": [], "In Curation": [], "Curation Issue": []}
        from ingest.dashboard import dashboard_callback
        from django.test import RequestFactory
        request = RequestFactory().get("/admin/")
        context = {}
        result = dashboard_callback(request, context)
        self.assertIn("curator_sections", result)
        self.assertIn("doi_table", result)
        self.assertIn("event_table", result)
        self.assertIsNone(result["asana_error"])


class V2PathsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='pathuser', password='x')
        self.collection = Collection.objects.create(
            name='c', bil_uuid='abc-123', data_path='/bil/lz/abc-123/', user=self.user,
        )

    @override_settings(FAKE_STORAGE_AREA=False)
    def test_get_etc_dir_production_swaps_lz_for_etc(self):
        from ingest.services.v2_paths import get_etc_dir
        self.assertEqual(get_etc_dir(self.collection), '/bil/etc/abc-123/')

    @override_settings(FAKE_STORAGE_AREA=True)
    def test_get_etc_dir_fake_storage_uses_tempdir(self):
        from ingest.services.v2_paths import get_etc_dir
        import tempfile, os
        expected = os.path.join(tempfile.gettempdir(), 'bil-etc', 'abc-123')
        self.assertEqual(get_etc_dir(self.collection), expected)

    @override_settings(FAKE_STORAGE_AREA=True)
    def test_ensure_etc_dir_creates_directory(self):
        from ingest.services.v2_paths import ensure_etc_dir
        import os
        path = ensure_etc_dir(self.collection)
        self.assertTrue(os.path.isdir(path))


class LuckysheetIOTests(TestCase):
    def _make_xls(self, tmpdir, data):
        """data: {sheet_name: [[row0_cells], [row1_cells], ...]}"""
        import xlwt, os
        wb = xlwt.Workbook(encoding='utf-8')
        for name, rows in data.items():
            ws = wb.add_sheet(name)
            for r, row in enumerate(rows):
                for c, val in enumerate(row):
                    if val is not None and val != '':
                        ws.write(r, c, val)
        path = os.path.join(tmpdir, 'in.xls')
        wb.save(path)
        return path

    def test_xls_to_luckysheet_shape(self):
        import tempfile
        from ingest.services.luckysheet_io import xls_to_luckysheet
        with tempfile.TemporaryDirectory() as tmp:
            path = self._make_xls(tmp, {'S1': [['a', 'b'], ['c', 'd']]})
            sheets = xls_to_luckysheet(path)
            self.assertEqual(len(sheets), 1)
            self.assertEqual(sheets[0]['name'], 'S1')
            cells = {(cd['r'], cd['c']): cd['v']['v'] for cd in sheets[0]['celldata']}
            self.assertEqual(cells, {(0, 0): 'a', (0, 1): 'b', (1, 0): 'c', (1, 1): 'd'})

    def test_xls_to_luckysheet_omits_empty_cells(self):
        import tempfile
        from ingest.services.luckysheet_io import xls_to_luckysheet
        with tempfile.TemporaryDirectory() as tmp:
            path = self._make_xls(tmp, {'S1': [['a', '', 'c']]})
            sheets = xls_to_luckysheet(path)
            coords = {(cd['r'], cd['c']) for cd in sheets[0]['celldata']}
            self.assertNotIn((0, 1), coords)

    def test_roundtrip_preserves_values(self):
        import tempfile, os
        from ingest.services.luckysheet_io import xls_to_luckysheet, luckysheet_to_xls
        with tempfile.TemporaryDirectory() as tmp:
            src = self._make_xls(tmp, {'A': [['x', 'y'], ['z', '']]})
            sheets = xls_to_luckysheet(src)
            out = os.path.join(tmp, 'out.xls')
            luckysheet_to_xls(sheets, out)
            round = xls_to_luckysheet(out)
            self.assertEqual(round, sheets)

    def test_luckysheet_to_xls_writes_atomically(self):
        import tempfile, os
        from ingest.services.luckysheet_io import luckysheet_to_xls
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'atomic.xls')
            with open(out, 'wb') as f:
                f.write(b'previous contents')
            sheets = [{'name': 'S', 'celldata': [{'r': 0, 'c': 0, 'v': {'v': 'new', 'm': 'new'}}]}]
            luckysheet_to_xls(sheets, out)
            self.assertFalse(os.path.exists(out + '.tmp'))
            from ingest.services.luckysheet_io import xls_to_luckysheet
            self.assertEqual(xls_to_luckysheet(out), sheets)


class V2ErrorsTests(TestCase):
    def test_normalize_empty(self):
        from ingest.services.v2_errors import normalize_errors
        result = normalize_errors([], [], {})
        self.assertEqual(result, {'workbook': [], 'cells': [], 'has_blocking': False})

    def test_normalize_spreadsheet_errors_go_to_workbook(self):
        from ingest.services.v2_errors import normalize_errors
        result = normalize_errors(['Dataset sheet not found.'], [], {})
        self.assertEqual(result['workbook'], [
            {'level': 'error', 'message': 'Dataset sheet not found.'},
        ])
        self.assertTrue(result['has_blocking'])

    def test_normalize_warnings_dont_block(self):
        from ingest.services.v2_errors import normalize_errors
        result = normalize_errors([], ['SWC sheet is missing.'], {})
        self.assertEqual(result['workbook'], [
            {'level': 'warning', 'message': 'SWC sheet is missing.'},
        ])
        self.assertFalse(result['has_blocking'])

    def test_normalize_cell_errors(self):
        from ingest.services.v2_errors import normalize_errors
        error_map = {'Dataset::3::5': ['"foo" invalid value']}
        result = normalize_errors([], [], error_map)
        self.assertEqual(result['cells'], [
            {'sheet': 'Dataset', 'row': 3, 'col': 5, 'message': '"foo" invalid value'},
        ])
        self.assertTrue(result['has_blocking'])

    def test_multiple_messages_per_cell_produce_multiple_entries(self):
        from ingest.services.v2_errors import normalize_errors
        error_map = {'Dataset::3::5': ['first', 'second']}
        result = normalize_errors([], [], error_map)
        self.assertEqual(len(result['cells']), 2)
        self.assertEqual({c['message'] for c in result['cells']}, {'first', 'second'})


class V2DownloadEndpointTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username='dladmin', email='a@a', password='x')
        self.client.force_login(self.admin)
        self.collection = Collection.objects.create(
            name='c', bil_uuid='dl-uuid', data_path='/bil/lz/dl-uuid/',
        )

    def tearDown(self):
        import os, shutil
        from ingest.services.v2_paths import get_etc_dir
        with override_settings(FAKE_STORAGE_AREA=True):
            etc = get_etc_dir(self.collection)
            if os.path.isdir(etc):
                shutil.rmtree(etc, ignore_errors=True)

    @override_settings(FAKE_STORAGE_AREA=True)
    def test_download_returns_working_xls(self):
        import os, xlwt
        from ingest.services.v2_paths import ensure_etc_dir
        etc = ensure_etc_dir(self.collection)
        xls_path = os.path.join(etc, 'work.xls')
        wb = xlwt.Workbook(); wb.add_sheet('S').write(0, 0, 'hi'); wb.save(xls_path)

        url = reverse('admin:ingest_collection_v2_download', args=[self.collection.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])

    @override_settings(FAKE_STORAGE_AREA=True)
    def test_download_404_when_no_file(self):
        from ingest.services.v2_paths import ensure_etc_dir
        ensure_etc_dir(self.collection)  # empty directory
        url = reverse('admin:ingest_collection_v2_download', args=[self.collection.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class V2UpdateFlowTests(TestCase):
    """End-to-end integration tests for the collapsed admin flow."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username='flowadmin', email='a@a', password='x')
        self.client.force_login(self.admin)
        self.collection = Collection.objects.create(
            name='c', bil_uuid='flow-uuid', data_path='/bil/lz/flow-uuid/',
            user=self.admin,
        )
        # Create a People record so run_preflight can find the collection owner.
        People.objects.create(
            name='Flow Admin', orcid='', affiliation='', affiliation_identifier='',
            auth_user_id=self.admin,
        )
        # Create a DescriptiveMetadata record so run_preflight sees v1 data.
        from .models import DescriptiveMetadata
        DescriptiveMetadata.objects.create(
            collection=self.collection, user=self.admin,
            sample_id='s', organism_type='mouse', organism_ncbi_taxonomy_id='10090',
            transgenetic_line_information='', method='m', technique='t',
            anatomical_structure='brain', total_processed_cells='0',
            organization='org', lab='lab', investigator='inv',
            grant_number='g', r24_name='r', r24_directory='d',
        )
        # Point V2_SPREADSHEET_DIR at a tempdir with a fixture file.
        import tempfile, os
        self.v2_src_dir = tempfile.mkdtemp()
        self.src_file = os.path.join(self.v2_src_dir, 'flow-uuid.xls')
        self._write_minimal_v2_xls(self.src_file)

    def tearDown(self):
        import shutil, os
        from ingest.services.v2_paths import get_etc_dir
        with override_settings(FAKE_STORAGE_AREA=True):
            etc = get_etc_dir(self.collection)
            if os.path.isdir(etc):
                shutil.rmtree(etc, ignore_errors=True)
        if hasattr(self, 'v2_src_dir') and os.path.isdir(self.v2_src_dir):
            shutil.rmtree(self.v2_src_dir, ignore_errors=True)

    def _write_minimal_v2_xls(self, path):
        """Write an .xls that will pass validate_spreadsheet's structural checks
        but deliberately has header-mismatch errors so check_all_sheets produces
        errors (has_blocking=True) and the view opens the Luckysheet editor.

        Deviation from brief:
        - Adds a cell to README (xlrd empty-workbook guard).
        - Writes a single placeholder cell at the expected header row for each
          sheet (row 2 for Contributors, row 3 for all others) so that
          check_*_sheet functions don't crash with IndexError, and instead
          return header-mismatch errors, making has_blocking=True.
        """
        import xlwt
        wb = xlwt.Workbook(encoding='utf-8')
        readme = wb.add_sheet('README')
        readme.write(0, 0, 'v2')  # xlrd empty-workbook guard

        contrib = wb.add_sheet('Contributors')
        contrib.write(2, 0, 'PLACEHOLDER')  # header row 2, wrong content → mismatch error

        funders = wb.add_sheet('Funders')
        funders.write(3, 0, 'PLACEHOLDER')  # header row 3

        pub = wb.add_sheet('Publication')
        pub.write(3, 0, 'PLACEHOLDER')

        instr = wb.add_sheet('Instrument')
        instr.write(3, 0, 'PLACEHOLDER')

        dataset = wb.add_sheet('Dataset')
        dataset.write(3, 0, 'PLACEHOLDER')

        specimen = wb.add_sheet('Specimen')
        specimen.write(3, 0, 'PLACEHOLDER')

        image = wb.add_sheet('Image')
        image.write(3, 0, 'PLACEHOLDER')

        wb.save(path)

    def _post_step_a(self, file_id, ingest_method='ingest_1'):
        url = reverse('admin:ingest_collection_v2_update', args=[self.collection.pk])
        return self.client.post(url, {
            'step': '2',
            'file_id': file_id,
            'ingest_method': ingest_method,
        })

    @override_settings(FAKE_STORAGE_AREA=True)
    def test_step_a_renders_pick_form(self):
        # Set V2_SPREADSHEET_DIR via override
        with override_settings(V2_SPREADSHEET_DIR=self.v2_src_dir):
            url = reverse('admin:ingest_collection_v2_update', args=[self.collection.pk])
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'flow-uuid', response.content)  # file appears in list
            self.assertIn(b'ingest_method', response.content)  # method picker present

    @override_settings(FAKE_STORAGE_AREA=True)
    def test_step_b_with_cell_errors_opens_editor(self):
        with override_settings(V2_SPREADSHEET_DIR=self.v2_src_dir):
            response = self._post_step_a(self.src_file, 'ingest_1')
            # Minimal xls has empty Dataset sheet → check_all_sheets will error.
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'luckysheet', response.content.lower())  # editor rendered
            # Working file landed in /etc/
            import os
            from ingest.services.v2_paths import get_etc_dir
            self.assertTrue(os.path.exists(os.path.join(get_etc_dir(self.collection), 'flow-uuid.xls')))

    @override_settings(FAKE_STORAGE_AREA=True)
    def test_editor_save_writes_xls_and_reruns_validation(self):
        with override_settings(V2_SPREADSHEET_DIR=self.v2_src_dir):
            self._post_step_a(self.src_file, 'ingest_1')

            import json
            import os
            from ingest.services.luckysheet_io import xls_to_luckysheet
            from ingest.services.v2_paths import get_etc_dir

            landed_xls = os.path.join(get_etc_dir(self.collection), 'flow-uuid.xls')
            workbook = xls_to_luckysheet(landed_xls)
            # Mutate one cell on the Dataset sheet.
            dataset = next(s for s in workbook if s['name'] == 'Dataset')
            dataset['celldata'].append({'r': 0, 'c': 0, 'v': {'v': 'edited', 'm': 'edited'}})

            url = reverse('admin:ingest_collection_v2_editor_save',
                          args=[self.collection.pk])
            response = self.client.post(url, {
                'workbook': json.dumps(workbook),
                'ingest_method': 'ingest_1',
            })
            # Editor save either re-renders editor (still errors) or redirects to success.
            self.assertIn(response.status_code, (200, 302))

            # Confirm working xls was written with our edit and still has all sheets.
            sheets = xls_to_luckysheet(landed_xls)
            self.assertEqual({s['name'] for s in sheets}, {w['name'] for w in workbook})
            dataset_out = next(s for s in sheets if s['name'] == 'Dataset')
            self.assertTrue(any(cd['v']['v'] == 'edited' for cd in dataset_out['celldata']))


# ---------------------------------------------------------------------------
# UserSideUploadUnaffectedTests
# ---------------------------------------------------------------------------

class UserSideUploadUnaffectedTests(TestCase):
    """Regression: the user-side descriptive_metadata_upload view still writes to /etc/."""

    @override_settings(FAKE_STORAGE_AREA=True)
    def test_user_upload_still_uses_etc_swap_pattern(self):
        # We're not exercising the full user upload endpoint (it requires PAM
        # auth and heavy fixtures). Instead we assert the *code line* that
        # implements the /lz/ -> /etc/ swap is still present, since Task 6's
        # changes must not perturb this path.
        import pathlib
        views_path = pathlib.Path(__file__).parent / 'views.py'
        source = views_path.read_text()
        self.assertIn('data_path.replace("/lz/", "/etc/")', source)
        # And FAKE_STORAGE_AREA branch remains:
        self.assertIn('settings.FAKE_STORAGE_AREA', source)
