# The order that these fields appear in this list will affect the order that
# they appear on the Metadata Creation page
#
metadata_fields = [
    'collection',
    'project_name',
    'project_description',
    'background_strain',
    'taxonomy_name',
    'transgenic_line_name',
    'age',
    'age_unit',
    'sex',
    'organ',
    'organ_substructure',
    'assay',
    'slicing_direction',
    'image_map_style',
    'processing_level',
    'image_filename_pattern',
    'directory',
]

collection_fields = [
    'name',
    'description',
    'organization_name',
    'lab_name',
    'project_funder',
    'project_funder_id',
    'project',
]


# this is *user-supplied* metadata, although we omit the associated collection,
# since we grab that through other means.
required_metadata = [
    'sample_id',
    'organism_type',
    'organism_ncbi_taxonomy_id',
    'transgenetic_line_information',
    'modality',
    'method',
    'technique',
    'anatomical_structure',
    'total_processed_cells',
    'organization',
    'lab',
    'investigator',
    'grant_number',
    'r24_name',
    'r24_directory',
]

event_type = [
    'mail_tapes_to_bil',
    'tapes_received',
    'tapes_ready_for_QC',
    'moved_to_collection',
    'request_brainball',
    'mail_brainball_from_bil',
    'mail_brainball_to_bil',
    'received_brainball',
    'collection_created',
    'metadata_uploaded',
    'request_validation',
    'request_submission',
    'request_embargo',
    'collection_public',
    'request_withdrawl',
]
contributor_metadata = [
    'contributorName',
    'creator',
    'contributorType',
    'nameType',
    'nameIdentifier',
    'nameIdentifierScheme',
    'affiliation',
    'affiliationIdentifier',
    'affiliationIdentifierScheme',
]
funder_metadata = [
    'name',
    'funding_reference_identifier',
    'funding_reference_identifier_type',
    'award_number',
    'award_title',
]
publication_metadata = [
    'relatedIdentifier',
    'relatedIdentifierType',
    'pmcid',
    'relationType',
    'citation',
]
instrument_metadata = [
    'microscopeType',
    'microscopeManufacturerAndModel',
    'objectiveName',
    'objectiveImmersion',
    'objectiveNA',
    'objectiveMagnification',
    'detectorType',
    'detectorModel',
    'illuminationTypes',
    'illuminationWavelength',
    'detectionWavelength',
    'sampleTemperature',
]
dataset_metadata = [
    'bilDirectory',
    'title',
    'socialMedia',
    'subject',
    'subjectScheme',
    'rights',
    'rightsURI',
    'rightsIdentifier',
    'image',
    'generalModality',
    'technique',
    'other',
    'abstract',
    'methods',
    'technicalInfo',
]
specimen_metadata = [
    'localID',
    'species',
    'ncbiTaxonomy',
    'age',
    'ageUnit',
    'sex',
    'genotype',
    'organLocalID',
    'organName',
    'sampleLocalID',
    'atlas',
    'locations',
]
image_metadata = [
    'xAxis',
    'obliqueXdim1',
    'obliqueXdim2',
    'obliqueXdim3',
    'yAxis',
    'obliqueYdim1',
    'obliqueYdim2',
    'obliqueYdim3',
    'zAxis',
    'obliqueZdim1',
    'obliqueZdim2',
    'obliqueZdim3',
    'landmarkName',
    'landmarkX',
    'landmarkY',
    'landmarkZ',
    'Number',
    'displayColor',
    'Representation',
    'Flurophore',
    'stepSizeX',
    'stepSizeY',
    'stepSizeZ',
    'stepSizeT',
    'Channels',
    'Slices',
    'z',
    'Xsize',
    'Ysize',
    'Zsize',
    'Gbytes',
    'Files',
    'DimensionOrder',
]
datastate_metadata = [
    'level',
    'included',
    'location',
    'attributes',
    'description',
]
project_fields = [
    'name',
    'funded_by'
]
consortium_fields = [
    'shortname',
    'longname'
]
project_consortium_fields = [
    'project',
    'consortium'
]
