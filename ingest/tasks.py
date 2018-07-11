from __future__ import absolute_import, unicode_literals
from celery import shared_task
from fabric import Connection
from django.conf import settings
import os
import subprocess


@shared_task
def create_data_path(data_path):
    """ We create a staging area when we create a collection. """
    command = 'mkdir -p {}'.format(data_path)
    subprocess.call(command.split(" "))
    #c = Connection(
    #    host=settings.IMG_DATA_HOST, user=settings.IMG_DATA_USER, port=22)
    #c.run('mkdir -p {}'.format(data_path))


@shared_task
def delete_data_path(host_and_path):
    """ We delete a staging area when we create a collection. """
    data_path = host_and_path.split(":")[1]
    command = 'rm -fr {}'.format(data_path)
    subprocess.call(command.split(" "))
    #data_path = host_and_path.split(":")[1]
    #c = Connection(
    #    host=settings.IMG_DATA_HOST, user=settings.IMG_DATA_USER, port=22)
    #c.run(command)


@shared_task
def get_directory_size(host_and_path):
    pass
    #data_path = host_and_path.split(":")[1]
    #c = Connection(
    #    host=settings.IMG_DATA_HOST, user=settings.IMG_DATA_USER, port=22)
    #output = c.run('du -sh {}'.format(data_path))
    #stdout = output.stdout
    #dir_size = stdout.split('\t')[0]
    #return dir_size
