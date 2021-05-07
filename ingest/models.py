from django.db import models
from django.contrib.auth.models import User

class UUID(models.Model):
    """ A grouping of one or more datasets and associated metadata. """
    def __str__(self):
        return self.name

    # Required and the user should supply these
    useduuid = models.CharField(max_length=256, unique=True)


class Collection(models.Model):
    """ A grouping of one or more datasets and associated metadata. """
    def __str__(self):
        return self.name

    # Required and the user should supply these
    name = models.CharField(max_length=256, unique=True)
    description = models.TextField()

    #AI = 'AI'
    #CSHL = 'CSHL'
    #USC = 'USC'
    #PITT = 'PITT'
    #ORGANIZATION_CHOICES = (
    #    (CSHL, 'Cold Spring Harbor Laboratory'),
    #    (USC, 'University of Southern California'),
    #    (AI, 'Allen Institute'),
    #    (PITT, 'University of Pittsburgh'),
    #)
    #organization_name = models.CharField(
    #    max_length=256,
    #    choices=ORGANIZATION_CHOICES,
    #    default=AI,
    #    help_text=(
    #        "The institution where the data generator/submitter or other "
    #        "responsible person resides.")
    #)
    
    organization_name = models.CharField(
        max_length=256, help_text="The institution where the data generator/submitter or other responsible person resides." )
    lab_name = models.CharField(
        max_length=256, help_text="The lab or department subgroup")
    project_funder_id = models.CharField(
        max_length=256, help_text="The grant number")

    # Optional fields. The user doesn't need to supply these.
    project_funder = models.CharField(
        max_length=256, blank=True, default="NIH")
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
    def __str__(self):
        return self.project_name

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
    modality = models.CharField(max_length=256)
    method = models.CharField(max_length=256)
    technique = models.CharField(max_length=256)
    anatomical_structure = models.CharField(max_length=256)
    total_processed_cells = models.CharField(max_length=256)
    organization = models.CharField(max_length=256)
    lab = models.CharField(max_length=256)
    investigator = models.CharField(max_length=256)
    grant_number = models.CharField(max_length=256)
    r24_name = models.CharField(max_length=256)
    r24_directory = models.CharField(max_length=256)
    
class BilUser(models.Model):

    def __str__(self):
        return self.name

    name = models.CharField(max_length=256)
    orcid = models.CharField(max_length=256)
    affiliation = models.CharField(max_length=256)
    affiliation_identifier = models.CharField(max_length=256)
    auth_user_id = models.ForeignKey(auth_user, on_delete=models.SET_NULL, null = True, blank=True)

class ProgramOfficer(models.Model):
    def __str__(self):
        return self.name
    
    grant_number = models.CharField(max_length=256)
    user_id = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

class Project(models.Model):
    def __str__(self):
        return self.name
    
    project_pi = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    funded_by = models.CharField(max_length=256)
    is_biccn = models.BooleanField(default=False)
    
class ProjectCollections(models.Model):
    def __str__(self):
        return self.name
    project_id = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True)
    collection_id = models.ForeignKey(Collection, on_delete=models.SET_NULL, null=True, blank=True)

class ProjectUsers(models.Model):
    def __str__(self):
        return self.name
    project_id = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True)
    user_id = models.ForeignKey(BilUser, on_delete=models.SET_NULL, null = True, blank=True)
    is_pi = models.BooleanField(default=False)
    is_po = models.BooleanField(default=False)
    role = models.CharField(max_length=256)

class SecondaryData(models.Model):
    def __str__(self):
        return self.name
    primary_data_id = models.ForeignKey(Collection, on_delete=models.SET_NULL, null=True, blank=True) 
    secondary_data_id = models.ForeignKey(Collection, on_delete=models.SET_NULL, null=True, blank=True)

class Funder(models.Model)
    def __str__(self):
        return self.name
    name = models.CharField(max_length=256)
    funding_reference_identifier = models.CharField(max_length=256)
    funding_reference_identifier_type = models.CharField(max_length=256)
    award_number = models.CharField(max_length=256)
    award_title = models.CharField(max_length=256)
    grant_number = models.CharField(max_length=256)

class ProjectFunders(models.Model):
    def __str__(self):
        return self.name
    project_id = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True)
    funder_id = models.ForeignKey(Funder, on_delete=models.SET_NULL, null=True, blank=True)

class EventsLog(models.Model)
    collection_id = models.ForeignKey(Collection, on_delete=models.SET_NULL, null=True, blank=True)
    bil_user_id = models.ForeignKey(BilUser, on_delete=models.SET_NULL, null=True, blank=True)
    project_id = models.ForeignKey(Project, on_delete=models.SET_NULL, null = True, blank=True)
    event_type = models.CharField(max_length=64, default="", choices=[('mail_tapes_to_bil', 'Mail Tapes To BIL'), ('tapes_received', 'Tapes Received'), ('tapes_ready_for_qc', 'Tapes Ready For QC'), ('move_to_collection', 'Move To Collection'), ('request_brainball', 'Request Brainball'), ('Mail_brainball_from_bil', 'Mail Brainball From BIL'), ('mail_brainball_to_bil', 'Mail Brainball To BIL'), ('received_brainball', 'Received Brainball'), ('collection_created', 'Collection Created'), ('metadata_uploaded', 'Metadata Uploaded'), ('request_validation', 'Request Validation'), ('request_submission', 'Request Submission'), ('request_embargo', 'Request Embargo'), ('collection_public', 'Collection Public'), ('request_withdrawal', 'Request Withdrawal')])

