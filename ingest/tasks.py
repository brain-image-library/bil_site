from __future__ import absolute_import, unicode_literals
from celery import shared_task
from fabric import Connection
from django.conf import settings
import os
import subprocess
import pathlib
import tempfile

#

@shared_task
def create_data_path(data_path):
    """ We create a staging area when we create a collection. """
    command = 'mkdir -p {}'.format(data_path)
    print(command)
    subprocess.call(command.split(" "))
    data_path2=data_path.replace("/lz/","/etc/")
    command2 = 'mkdir -p {}'.format(data_path2)
    print(command2)
    subprocess.call(command2.split(" "))


@shared_task
def delete_data_path(host_and_path):
    """ We delete a staging area when we create a collection. """
    data_path = host_and_path.split(":")[1]
    command = 'rm -fr {}'.format(data_path)
    subprocess.call(command.split(" "))
    data_path2=data_path.replace("/lz/","/etc/")
    command2 = 'rm -fr {}'.format(data_path2)
    subprocess.call(command2.split(" "))


@shared_task
def run_analysis(host_and_path, metadata_dirs):
    analysis_results = {}
    # if anything sets this to false, then validation has failed
    analysis_results['type'] = 'Submit'
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
    # Run external validation script
    command = 'bil_submit.sh {}'.format(data_path)
    datapath2=data_path.replace("/lz/","/etc/")
    data_path_logdir= '{}'.format(datapath2)
    outfile = tempfile.NamedTemporaryFile(delete=False,dir=data_path_logdir)
    p2 = subprocess.Popen(command.split(" "), stdout=outfile)
    #p = subprocess.Popen(command.split(" "), stdout=subprocess.PIPE)
    analysis_results['output'] = outfile.name
    p2.wait()
    outfile.close()
    #Open the log file and read the contents
    f=open(analysis_results['output'], "r")
    for myline in f:
       if 'BIL-ERROR' in myline:
          analysis_results['valid'] = False
    f.close()

    return analysis_results

@shared_task
def run_validate(host_and_path, metadata_dirs):
    analysis_results = {}
    # if anything sets this to false, then validation has failed
    analysis_results['type'] = 'Validate'
    analysis_results['valid'] = True
    # get directory size
    data_path = host_and_path.split(":")[1]
    command = 'du -sh {}'.format(data_path)
    p1 = subprocess.Popen(command.split(" "), stdout=subprocess.PIPE)
    output = p1.communicate()[0].decode("utf-8")
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
    # Run external validation script
    command = 'bil_validate.sh {}'.format(data_path)
    datapath2=data_path.replace("/lz/","/etc/")
    data_path_logdir= '{}'.format(datapath2)
    outfile = tempfile.NamedTemporaryFile(delete=False,dir=data_path_logdir)
    p2 = subprocess.Popen(command.split(" "), stdout=outfile)
    #p = subprocess.Popen(command.split(" "), stdout=subprocess.PIPE)
    analysis_results['output'] = outfile.name
    p2.wait()
    outfile.close()
    #Open the log file and read the contents
    f=open(analysis_results['output'], "r")
    for myline in f:
       if 'BIL-ERROR' in myline:
          analysis_results['valid'] = False
    f.close()
           
    return analysis_results
