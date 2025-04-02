from django.db import models
from django.contrib.auth.models import User
from django.conf import settings


class UUID(models.Model):
    """ A grouping of one or more datasets and associated metadata. """
    def __str__(self):
        return self.name

    # Required and the user should supply these
    useduuid = models.CharField(max_length=256, unique=True)

class Project(models.Model):
    def __str__(self):
        return self.name
    name = models.CharField(max_length=256, default="Project Name")
    funded_by = models.CharField(max_length=256)
    is_biccn = models.BooleanField(default=False)

class Consortium(models.Model):
    short_name = models.CharField(max_length=256)
    long_name = models.CharField(max_length=1000)

    def __str__(self):
        return self.short_name 

class ProjectConsortium(models.Model):
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=False, null=True)
    consortium = models.ForeignKey(Consortium, on_delete=models.SET_NULL, null = True, blank=True)

class ProjectAssociation(models.Model):
    project = models.ForeignKey(Project, related_name='project', on_delete=models.SET_NULL, blank=False, null=True)
    parent_project = models.ForeignKey(Project, related_name='parent_project', on_delete=models.SET_NULL, blank=False, null=True)

class People(models.Model):
    def __str__(self):
        return self.name
    name = models.CharField(max_length=256)
    orcid = models.CharField(max_length=256)
    affiliation = models.CharField(max_length=256)
    affiliation_identifier = models.CharField(max_length=256)
    is_bil_admin = models.BooleanField(default=False)
    auth_user_id = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null = True, blank=True)

class Collection(models.Model):
    """ A grouping of one or more datasets and associated metadata. """
    def __str__(self):
        collreturn = "Collection Name: " + self.name + ' : BIL UUID: ' + self.bil_uuid
        return collreturn
        #return self.name
    # Required and the user should supply these
    name = models.CharField(max_length=256, unique=True)
    description = models.TextField()   
    organization_name = models.CharField(
        max_length=256, help_text="The institution where the data generator/submitter or other responsible person resides." )
    lab_name = models.CharField(
        max_length=256, help_text="The lab or department subgroup")
    project_funder_id = models.CharField(
        max_length=256, help_text="The grant number")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=False, null=True)
    # Optional fields. The user doesn't need to supply these.
    project_funder = models.CharField(
        max_length=256, blank=False, default="NIH")
    modality = models.CharField(max_length=256, blank=True, default="NIH")
    collection_type = models.CharField(max_length=256, blank=True, default="NIH")
    bil_uuid = models.CharField(max_length=256)
    # These fields are required but the user shouldn't control these
    data_path = models.CharField(max_length=256)
    # "locked" is used to prevent submitted data from being changed
    locked = models.BooleanField(default=False)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL, blank=True, null=True)
    # This is how we're initially tracking validation. Ultimately, we'll
    # probably want to break up validation into multiple tasks (e.g. checking
    # dataset size, verifying valid TIFF/JPEG2000 files, etc), in which case
    # we'll probably want to set up a one-to-many relationship w/ task IDs.
    celery_task_id_submission = models.CharField(max_length=256)
    celery_task_id_validation = models.CharField(max_length=256)
    NOT_SUBMITTED = 'NOT_SUBMITTED'
    NOT_VALIDATED = 'NOT_VALIDATED'
    SUCCESS = 'SUCCESS'
    PENDING = 'PENDING'
    FAILED = 'FAILED'
    STATUS_CHOICES_SUBMISSION = (
        (NOT_SUBMITTED, 'Not submitted'),
        (SUCCESS, 'Success'),
        (PENDING, 'Pending'),
        (FAILED, 'Failed'),
    )
    STATUS_CHOICES_VALIDATION = (
        (NOT_VALIDATED, 'Not validated'),
        (SUCCESS, 'Success'),
        (PENDING, 'Pending'),
        (FAILED, 'Failed'),
    )
    submission_status = models.CharField(
        max_length=256,
        choices=STATUS_CHOICES_SUBMISSION,
        default=NOT_SUBMITTED,
    )
    validation_status = models.CharField(
        max_length=256,
        choices=STATUS_CHOICES_VALIDATION,
        default=NOT_VALIDATED,
    )
    collection_type = models.CharField(
        max_length=256)

class Sheet(models.Model):
    def __str__(self):
        return self.filename
    filename = models.CharField(max_length=500)
    date_uploaded = models.DateTimeField(auto_now_add=True, blank=True)
    collection = models.ForeignKey(Collection,
        on_delete=models.SET_NULL, blank=False, null=True)
    ingest_method = models.CharField(max_length=10, blank=False, null=True)

class Dataset(models.Model):
    bildirectory = models.CharField(max_length=256)
    title = models.CharField(max_length=500)
    socialmedia = models.CharField(max_length=500, blank=True)
    subject = models.CharField(max_length=256, blank=True)
    subjectscheme = models.CharField(max_length=256, blank=True)
    rights = models.CharField(max_length=256)
    rightsuri = models.CharField(max_length=256)
    rightsidentifier = models.CharField(max_length=256)
    dataset_image = models.CharField(max_length=256, blank=True)
    generalmodality = models.CharField(max_length=256, blank=True)
    technique = models.CharField(max_length=256, blank=True)
    other = models.CharField(max_length=256, blank=True)
    abstract = models.CharField(max_length=3000)
    methods = models.CharField(max_length=2000, blank=True)
    technicalinfo = models.CharField(max_length=3000, blank=True)
    sheet = models.ForeignKey(Sheet, on_delete=models.SET_NULL, blank=True, null=True)
    specimen_ingest_method_4 = models.IntegerField(blank=True, null=True) # this is not a proper fk. this is just to avoid adding a join table.
    doi = models.CharField(max_length=256, blank=True)
    dataset_size = models.CharField(max_length=256, blank=True, null=True)
    number_of_files = models.BigIntegerField(blank=True, null=True)
    #def __str__(self):
    #    return self.title

    #class Meta:
    #    verbose_name = 'Dataset'
    #    verbose_name_plural = 'Datasets'

    #@classmethod
    #def autocomplete_search_fields(cls):
    #    return ['dataset__icontains']

class ImageMetadata(models.Model):
    # The meat of the image metadata bookkeeping. This is all the relevant
    # information about a given set of imaging data.
    def __str__(self):
        return self.project_name

    # This can be used for multiple drop down choices
    UNKNOWN = 'Unknown'

    # Required and the user should supply these
    project_name = models.CharField(
        max_length=256,
        help_text=('The project name does not have to be the '
                   'same as the NIH project name.'))
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    project_description = models.TextField()
    background_strain = models.CharField(
        max_length=256, help_text="e.g. C57BL/6J")
    image_filename_pattern = models.CharField(max_length=256)
    directory = models.CharField(
        max_length=4096,
        help_text=(
            "relative to the landing zone, the top level directory name of "
            "this dataset, e.g. './mouse_dataset_0001'"),
    )

    # These fields are required but the user shouldn't control these
    #
    # "locked" is used to prevent submitted data from being changed
    locked = models.BooleanField(default=False)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True, blank=True)
    last_edited = models.DateTimeField(auto_now=True, blank=True)

    # Optional fields. The user doesn't need to supply these.
    taxonomy_name = models.CharField(max_length=256, blank=True, default="")
    transgenic_line_name = models.CharField(
        max_length=256, blank=True, default="")
    age = models.IntegerField(blank=True, null=True)
    DAY = 'DAY'
    WEEK = 'WEEK'
    MONTH = 'MONTH'
    AGE_UNIT_CHOICES = (
        (DAY, 'Day'),
        (WEEK, 'Week'),
        (MONTH, 'Month'),
        (UNKNOWN, 'Unknown'),
    )
    age_unit = models.CharField(
        max_length=256,
        choices=AGE_UNIT_CHOICES,
        default=UNKNOWN)
    MALE = 'MALE'
    FEMALE = 'FEMALE'
    SEX_CHOICES = (
        (MALE, 'Male'),
        (FEMALE, 'Female'),
        (UNKNOWN, 'Unknown'),
    )
    sex = models.CharField(
        max_length=256,
        choices=SEX_CHOICES,
        default=UNKNOWN,
    )
    organ = models.CharField(max_length=256, blank=True, default="Brain")
    organ_substructure = models.CharField(
        max_length=256,
        blank=True,
        default="Whole brain",
        help_text="e.g. hippocampus, prefrontal cortex")
    assay = models.CharField(
        max_length=256,
        blank=True,
        default="",
        help_text="e.g. smFISH, fMOST, MouseLight")
    CORONAL = 'CORONAL'
    SAGITTAL = 'SAGITTAL'
    AXIAL = 'AXIAL'
    SLICING_DIRECTION_CHOICES = (
        (CORONAL, 'Coronal'),
        (SAGITTAL, 'Sagittal'),
        (AXIAL, 'Axial'),
        (UNKNOWN, 'Unknown'),
    )
    slicing_direction = models.CharField(
        max_length=256,
        choices=SLICING_DIRECTION_CHOICES,
        default=UNKNOWN,
    )
    MAPZ = 'MAPZ'
    MAPXY = 'MAPXY'
    MAPYX = 'MAPYX'
    MAPXYZ = 'MAPXYZ'
    MAPYXZ = 'MAPYXZ'
    MAPZXY = 'MAPZXY'
    MAPZYX = 'MAPZYX'
    MAP_CHOICES = (
        (MAPZ, 'Map Z'),
        (MAPXY, 'Map XY'),
        (MAPYX, 'Map YX'),
        (MAPXYZ, 'Map XYZ'),
        (MAPYXZ, 'Map YXZ'),
        (MAPZXY, 'Map ZXY'),
        (MAPZYX, 'Map ZYX'),
        (MAPZYX, 'Map ZYX'),
        (UNKNOWN, 'Unknown'),
    )
    image_map_style = models.CharField(
        max_length=256,
        choices=MAP_CHOICES,
        default=UNKNOWN,
    )

    PROC1 = 'ORIGINAL_CAPTURE_UNPROCESSED'
    PROC2 = 'ORIGINAL_CAPTURE_AUTOSTITCHED'
    PROC3 = 'FULL_CAPTURE_REFORMATED'
    PROC4 = 'FULL_CAPTURE_STITCHED_REFORMATTED'
    PROC5 = 'PROCESSED'
    PROCESSING_CHOICES = (
        (PROC1, 'Original Capture Unprocessed'),
        (PROC2, 'Original Capture Autostitched'),
        (PROC3, 'Full Capture Reformatted'),
        (PROC4, 'Full Capture Stitched Reformatted'),
        (PROC5, 'Processed'),
        (UNKNOWN, 'Unknown'),
    )

    processing_level = models.CharField(
        max_length=256,
        choices=PROCESSING_CHOICES,
        default=UNKNOWN,
    )

class DescriptiveMetadata(models.Model):
    # This is the exact nomenclature used by BICCN.
    # The meat of the image metadata bookkeeping. This is all the relevant
    # information about a given set of imaging data.
    #def __str__(self):
    #    return self.project_name

    # These fields are required but the user shouldn't control these
    #
    # "locked" is used to prevent submitted data from being changed
    locked = models.BooleanField(default=False)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True, blank=True)
    last_edited = models.DateTimeField(auto_now=True, blank=True)
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    #
    # These fields are supplied in the BICCN spreasdheet
    sample_id = models.CharField(max_length=256)
    organism_type = models.CharField(max_length=256)
    organism_ncbi_taxonomy_id = models.CharField(max_length=256)
    transgenetic_line_information = models.CharField(max_length=256)
    modality = models.CharField(max_length=256, null=True, blank=True)
    method = models.CharField(max_length=256)
    technique = models.CharField(max_length=256)
    anatomical_structure = models.CharField(max_length=256)
    total_processed_cells = models.CharField(max_length=256)
    organization = models.CharField(max_length=256)
    lab = models.CharField(max_length=256)
    investigator = models.CharField(max_length=256)
    grant_number = models.CharField(max_length=256)
    dataset_uuid = models.CharField(max_length=256, null=True, blank=True)
    r24_name = models.CharField(max_length=256)
    r24_directory = models.CharField(max_length=256)

class DataGroup(models.Model):
    data_group_list_id = models.IntegerField()
    dm_id = models.ForeignKey(DescriptiveMetadata, on_delete=models.CASCADE, null = False)

class ProjectPeople(models.Model):
    def __str__(self):
        return self.project_id.name
    project_id = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True)
    people_id = models.ForeignKey(People, on_delete=models.SET_NULL, null = True, blank=True)
    is_pi = models.BooleanField(default=False)
    is_po = models.BooleanField(default=False)
    doi_role = models.CharField(max_length=256)

class Funder(models.Model):
    fundername = models.CharField(max_length=256)
    funding_reference_identifier = models.CharField(max_length=256, blank=True)
    funding_reference_identifier_type = models.CharField(max_length=256, blank=True)
    award_number = models.CharField(max_length=256, blank=True)
    award_title = models.CharField(max_length=256, blank=True)
    sheet = models.ForeignKey(Sheet, on_delete=models.SET_NULL, blank=True, null=True)

class EventsLog(models.Model):
    collection_id = models.ForeignKey(Collection, on_delete=models.SET_NULL, null=True, blank=True)
    people_id = models.ForeignKey(People, on_delete=models.SET_NULL, null=True, blank=True)
    project_id = models.ForeignKey(Project, on_delete=models.SET_NULL, null = True, blank=True)
    notes = models.CharField(max_length=256)
    timestamp = models.DateTimeField()
    #Add field for embargo information
    event_type = models.CharField(max_length=64, default="", choices=[('mail_tapes_to_bil', 'Mail Tapes To BIL'), ('tapes_received', 'Tapes Received'), ('tapes_ready_for_qc', 'Tapes Ready For QC'), ('move_to_collection', 'Move To Collection'), ('request_brainball', 'Request Brainball'), ('Mail_brainball_from_bil', 'Mail Brainball From BIL'), ('mail_brainball_to_bil', 'Mail Brainball To BIL'), ('received_brainball', 'Received Brainball'), ('collection_created', 'Collection Created'), ('metadata_uploaded', 'Metadata Uploaded'), ('request_validation', 'Request Validation'), ('request_submission', 'Request Submission'), ('request_embargo', 'Request Embargo'), ('collection_public', 'Collection Public'), ('request_withdrawal', 'Request Withdrawal'), ('data_curated', 'Data Curated'), ('collection_validated', 'Collected Validated'), ('user_action_required', 'User Action Required'),])

class DatasetEventsLog(models.Model):
    dataset_id = models.ForeignKey(Dataset, on_delete=models.SET_NULL, null=True, blank=True)
    collection_id = models.ForeignKey(Collection, on_delete=models.SET_NULL, null=True, blank=True)
    project_id = models.ForeignKey(Project, on_delete=models.SET_NULL, null = True, blank=True)
    notes = models.CharField(max_length=256)
    timestamp = models.DateTimeField()
    event_type = models.CharField(max_length=64, default="", choices=[('uploaded', 'Uploaded'),('validated', 'Validated'), ('curated', 'Curated'), ('doi', 'DOI'), ('public', 'Public')])
    

class Contributor(models.Model):
    contributorname = models.CharField(max_length=256)
    creator = models.CharField(max_length=100)
    contributortype = models.CharField(max_length=256)
    nametype = models.CharField(max_length=256)
    nameidentifier = models.CharField(max_length=256, blank = True)
    nameidentifierscheme = models.CharField(max_length=256, blank = True)
    affiliation = models.CharField(max_length=256)
    affiliationidentifier = models.CharField(max_length=256)
    affiliationidentifierscheme = models.CharField(max_length=256)
    sheet = models.ForeignKey(Sheet, on_delete=models.SET_NULL, blank=True, null=True)

class Publication(models.Model):
    relatedidentifier = models.CharField(max_length=256, blank=True)
    relatedidentifiertype = models.CharField(max_length=256, blank=True)
    pmcid = models.CharField(max_length=256, blank=True)
    relationtype = models.CharField(max_length=256, blank=True)
    citation = models.CharField(max_length=1500, blank=True)
    sheet = models.ForeignKey(Sheet, on_delete=models.SET_NULL, blank=True, null=True)
    data_set = models.ForeignKey(Dataset, on_delete=models.SET_NULL, blank=True, null=True)

class Specimen(models.Model):
    localid = models.CharField(max_length=256, blank=True)
    species = models.CharField(max_length=256)
    ncbitaxonomy = models.CharField(max_length=256)
    age = models.CharField(max_length=256)
    ageunit = models.CharField(max_length=256)
    sex = models.CharField(max_length=256)
    genotype = models.CharField(max_length=256, blank=True)
    organlocalid = models.CharField(max_length=256, blank=True)
    organname = models.CharField(max_length=256, blank=True)
    samplelocalid = models.CharField(max_length=256)
    atlas = models.CharField(max_length=256, blank=True)
    locations = models.CharField(max_length=256, blank=True)
    sheet = models.ForeignKey(Sheet, on_delete=models.SET_NULL, blank=True, null=True)
    data_set = models.ForeignKey(Dataset, on_delete=models.SET_NULL, blank=True, null=True)

class Image(models.Model):
    xaxis = models.CharField(max_length=256)
    obliquexdim1 = models.CharField(max_length=256, blank=True)
    obliquexdim2 = models.CharField(max_length=256, blank=True)
    obliquexdim3 = models.CharField(max_length=256, blank=True)
    yaxis = models.CharField(max_length=256)
    obliqueydim1 = models.CharField(max_length=256, blank=True)
    obliqueydim2 = models.CharField(max_length=256, blank=True)
    obliqueydim3 = models.CharField(max_length=256, blank=True)
    zaxis = models.CharField(max_length=256)
    obliquezdim1 = models.CharField(max_length=256, blank=True)
    obliquezdim2 = models.CharField(max_length=256, blank=True)
    obliquezdim3 = models.CharField(max_length=256, blank=True)
    landmarkname = models.CharField(max_length=256, blank=True)
    landmarkx = models.CharField(max_length=256, blank=True)
    landmarky = models.CharField(max_length=256, blank=True)
    landmarkz = models.CharField(max_length=256, blank=True)
    number = models.CharField(max_length=256)
    displaycolor = models.CharField(max_length=256)
    representation = models.CharField(max_length=256, blank=True)
    flurophore = models.CharField(max_length=256, blank=True)
    stepsizex = models.CharField(max_length=256)
    stepsizey = models.CharField(max_length=256)
    stepsizez = models.CharField(max_length=256, blank=True)
    stepsizet = models.CharField(max_length=256, blank=True)
    channels = models.CharField(max_length=256, blank=True)
    slices = models.CharField(max_length=256, blank=True)
    z = models.CharField(max_length=256, blank=True)
    xsize = models.CharField(max_length=256, blank=True)
    ysize = models.CharField(max_length=256, blank=True)
    zsize = models.CharField(max_length=256, blank=True)
    gbytes = models.CharField(max_length=256, blank=True)
    files = models.CharField(max_length=256, blank=True)
    dimensionorder = models.CharField(max_length=256, blank=True)
    sheet = models.ForeignKey(Sheet, on_delete=models.SET_NULL, blank=True, null=True)
    data_set = models.ForeignKey(Dataset, on_delete=models.SET_NULL, blank=True, null=True)
    specimen = models.ForeignKey(Specimen, on_delete=models.SET_NULL, blank=True, null=True)

class DataState(models.Model):
    level = models.CharField(max_length=256)
    included = models.BooleanField(default=False)
    location = models.CharField(max_length=256)
    attributes = models.CharField(max_length=256)
    description = models.CharField(max_length=1000)
    sheet = models.ForeignKey(Sheet, on_delete=models.SET_NULL, blank=True, null=True)
    data_set = models.ForeignKey(Dataset, on_delete=models.SET_NULL, blank=True, null=True)
    specimen = models.ForeignKey(Specimen, on_delete=models.SET_NULL, blank=True, null=True)
    data_set = models.ForeignKey(Dataset, on_delete=models.SET_NULL, blank=True, null=True)

class Instrument(models.Model):
    microscopetype = models.CharField(max_length=256)
    microscopemanufacturerandmodel = models.CharField(max_length=1000)
    objectivename = models.CharField(max_length=256, blank=True)
    objectiveimmersion = models.CharField(max_length=256, blank=True)
    objectivena = models.CharField(max_length=256, blank=True)
    objectivemagnification = models.CharField(max_length=256, blank=True)
    detectortype = models.CharField(max_length=256, blank=True)
    detectormodel = models.CharField(max_length=256, blank=True)
    illuminationtypes = models.CharField(max_length=256, blank=True)
    illuminationwavelength = models.CharField(max_length=256, blank=True)
    detectionwavelength = models.CharField(max_length=256, blank=True)
    sampletemperature = models.CharField(max_length=256, blank=True)
    sheet = models.ForeignKey(Sheet, on_delete=models.SET_NULL, blank=True, null=True)
    data_set = models.ForeignKey(Dataset, on_delete=models.SET_NULL, blank=True, null=True)
    specimen = models.ForeignKey(Specimen, on_delete=models.SET_NULL, blank=True, null=True)
    
class MetadataVersion(models.Model):
    dataset_id_dm = models.ForeignKey(DescriptiveMetadata, on_delete = models.SET_NULL, blank = True, null = True)
    dataset_id_ds = models.ForeignKey(Dataset, on_delete=models.SET_NULL, blank=True, null=True)
    metadata_version = models.CharField(max_length=64, blank=True, null=True)
    dataset_doi = models.CharField(max_length=512, blank=True, null=True)
    dataset_status= models.CharField(max_length=256, blank=True, null=True)
    event = models.ForeignKey(EventsLog, on_delete=models.SET_NULL, blank=True, null=True)

class SWC(models.Model):
    tracingFile = models.CharField(max_length=256, blank=True, null=True)
    sourceData = models.CharField(max_length=256, blank=True, null=True)
    sourceDataSample = models.CharField(max_length=256, blank=True, null=True)
    sourceDataSubmission = models.CharField(max_length=256, blank=True, null=True)
    coordinates = models.CharField(max_length=256, blank=True, null=True)
    coordinatesRegistration = models.CharField(max_length=256, blank=True, null=True)
    brainRegion = models.CharField(max_length=256, blank=True, null=True)
    brainRegionAtlas = models.CharField(max_length=256, blank=True, null=True)
    brainRegionAtlasName = models.CharField(max_length=256, blank=True, null=True)
    brainRegionAxonalProjection = models.CharField(max_length=256, blank=True, null=True)
    brainRegionDendriticProjection = models.CharField(max_length=256, blank=True, null=True)
    neuronType = models.CharField(max_length=256, blank=True, null=True)
    segmentTags = models.CharField(max_length=256, blank=True, null=True)
    proofreadingLevel = models.CharField(max_length=256, blank=True, null=True)
    notes =  models.TextField()
    swc_uuid = models.CharField(max_length = 1000, blank=False, null=True)
    data_set = models.ForeignKey(Dataset, on_delete=models.SET_NULL, blank=True, null=True)
    sheet = models.ForeignKey(Sheet, on_delete=models.SET_NULL, blank=True, null=True)

class BIL_ID(models.Model):
    bil_id = models.CharField(max_length=256, blank=True, null=True)
    v1_ds_id = models.ForeignKey(DescriptiveMetadata, on_delete=models.SET_NULL, blank=True, null=True)
    v2_ds_id = models.ForeignKey(Dataset,  related_name='v2_ds_id', on_delete=models.SET_NULL, blank=True, null=True)
    metadata_version = models.IntegerField(blank=True, null=True)
    doi = models.BooleanField(default=False)
    def __str__(self):
        return self.bil_id

    class Meta:
        verbose_name = 'BIL ID'
        verbose_name_plural = 'BIL IDs'

    @classmethod
    def autocomplete_search_fields(cls):
        return ['bil_id__icontains']

class DatasetLinkage(models.Model):
    data_id_1_bil = models.ForeignKey(BIL_ID, on_delete=models.SET_NULL, null=True, blank=True)
    code_id = models.CharField(max_length=64, default="", choices=[('bil', 'BIL'), ('nemo', 'Nemo'),('dandi', 'Dandi'), ('cubietissue', 'CubieTissue')]) 
    data_id_2 = models.CharField(max_length=256, blank=True, null=True)
    relationship = models.CharField(max_length=64, default="", choices=[('sequence data', 'Sequence Data'), ('neuron tracing', 'Neuron Tracing'), ('derived_data', 'Derived Data'), ('raw', 'Raw'), ('aligned', 'Aligned')]) 
    description = models.TextField(blank=True, null=True)
    linkage_date = models.DateField(null=True, blank=True)

class BIL_Specimen_ID(models.Model):
    bil_spc_id = models.CharField(max_length=256, blank=True, null=True)
    specimen_id = models.ForeignKey(Specimen, on_delete=models.SET_NULL, null = True, blank=True)
    def __str__(self):
        return self.bil_spc_id

class BIL_Instrument_ID(models.Model):
    bil_ins_id = models.CharField(max_length=256, blank=True, null=True)
    instrument_id = models.ForeignKey(Instrument, on_delete=models.SET_NULL, null = True, blank=True)

class BIL_Project_ID(models.Model):
    bil_prj_id = models.CharField(max_length=256, blank=True, null=True)
    project_id = models.ForeignKey(Project, on_delete=models.SET_NULL, null = True, blank=True)

class SpecimenLinkage(models.Model):
    specimen_id = models.ForeignKey(BIL_Specimen_ID, on_delete=models.SET_NULL, null=True, blank=True)
    specimen_id_2 = models.CharField(max_length=256, blank=True, null=True)
    code_id = models.CharField(max_length=64, default="", choices=[('cubie_tissue', 'Cubie Tissue')])
    specimen_category = models.CharField(max_length=64, default="", choices=[('tissue', 'Tissue'), ('roi', 'ROI'), ('slab', 'Slab'), ('donor', 'Donor'), ('section', 'Section')]) 

class ConsortiumTag(models.Model):
    consortium = models.ForeignKey(Consortium, on_delete=models.CASCADE, related_name='tags')
    tag = models.CharField(max_length=256)

    def __str__(self):
        return f"{self.consortium.short_name} - {self.tag}"
class DatasetTag(models.Model):
    tag = models.ForeignKey(ConsortiumTag, on_delete=models.CASCADE)  # Reference to ConsortiumTag
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='tags')
    bil_id = models.ForeignKey(BIL_ID, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.tag.tag} (Dataset: {self.dataset})"
