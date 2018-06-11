from __future__ import absolute_import, unicode_literals
from celery import shared_task
from fabric import Connection
import os


@shared_task
def create_data_path(data_path):
    c = Connection(host='dxc.psc.edu', port=22)
    c.run('mkdir -p {}'.format(data_path))
