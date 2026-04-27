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
from django.test import TestCase, Client
from django.contrib.auth.models import User
from .models import Project, People, ProjectPeople, Consortium

from ingest.views import (
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
