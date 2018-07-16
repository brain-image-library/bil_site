from __future__ import absolute_import, unicode_literals
from celery import shared_task
from fabric import Connection
from django.conf import settings
import os
import subprocess
import pathlib


@shared_task
def create_data_path(data_path):
    """ We create a staging area when we create a collection. """
    command = 'mkdir -p {}'.format(data_path)
    subprocess.call(command.split(" "))


@shared_task
def delete_data_path(host_and_path):
    """ We delete a staging area when we create a collection. """
    data_path = host_and_path.split(":")[1]
    command = 'rm -fr {}'.format(data_path)
    subprocess.call(command.split(" "))


@shared_task
def run_analysis(host_and_path, metadata_dirs):
    analysis_results = {}
    # if anything sets this to false, then validation has failed
    analysis_results['valid'] = True
    # get directory size
    data_path = host_and_path.split(":")[1]
    command = 'du -sh {}'.format(data_path)
    p = subprocess.Popen(command.split(" "), stdout=subprocess.PIPE)
    output = p.communicate()[0].decode("utf-8")
    dir_size = output.split('\t')[0]
    analysis_results['dir_size'] = dir_size
    # make sure metadata directories exist
    invalid_metadata_directories = []
    for md in metadata_dirs:
        full_metadata_directory = pathlib.Path(data_path, md)
        if not full_metadata_directory.is_dir():
            invalid_metadata_directories.append(full_metadata_directory.as_posix())
            analysis_results['valid'] = False
    analysis_results['invalid_metadata_directories'] = invalid_metadata_directories
    return analysis_results
