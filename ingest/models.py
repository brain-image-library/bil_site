from django.db import models


class MinimalImgMetadata(models.Model):
    def __str__(self):
        return self.project_name
    AI = 'AI'
    CSHL = 'CSHL'
    USC = 'USC'
    ORGANIZATION_CHOICES = (
        (CSHL, 'Cold Spring Harbor Laboratory'),
        (USC, 'University of Southern California'),
        (AI, 'Allen Institute'),
    )
    organization_name = models.CharField(
        max_length=200,
        choices=ORGANIZATION_CHOICES,
        default=AI,
    )
    project_name = models.CharField(max_length=200)
    project_description = models.CharField(max_length=200)
    project_funder_id = models.CharField(max_length=200)
    background_strain = models.CharField(max_length=200)
    image_filename_pattern = models.CharField(max_length=200)
    submitter_email = models.EmailField()
