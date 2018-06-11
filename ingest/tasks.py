from __future__ import absolute_import, unicode_literals
from celery import shared_task
import os


@shared_task
def create_data_path(data_path):
    if not os.path.exists(data_path):
        os.makedirs(data_path)
