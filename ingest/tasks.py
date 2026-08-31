from __future__ import absolute_import, unicode_literals
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
import os
import subprocess
import pathlib
import tempfile

VALIDATION_FAILURE_EMAIL_RECIPIENT = "ltuite96@psc.edu"
VALIDATION_FAILURE_EMAIL_SENDER = "noreply@psc.edu"

#

@shared_task
def create_data_path(data_path,username):
    """ We create a staging area when we create a collection. """
    lzrootdir='/bil/lz/{}'.format(username)
    if not os.path.isdir(lzrootdir):
       rootmkdircmd='mkdir -p {}'.format(lzrootdir)
       subprocess.call(rootmkdircmd.split(" "))
       rootcmd2='chown bil:bil {}'.format(lzrootdir)
       subprocess.call(rootcmd2.split(" "))
       rootcmd3='chmod 770 {}'.format(lzrootdir)
       subprocess.call(rootcmd3.split(" "))
       rootcmd4='setfacl -m u:{}:rx {}'.format(username,lzrootdir)
       subprocess.call(rootcmd4.split(" "))
    command = 'mkdir -p {}'.format(data_path)
    subprocess.call(command.split(" "))
    chowncmd2='chown bil:bil {}'.format(data_path)
    subprocess.call(chowncmd2.split(" "))

    command1 = 'chmod 700 {}'.format(data_path)
    subprocess.call(command1.split(" "))
    command2 = 'setfacl -m u:{}:rwx {}'.format(username,data_path)
    subprocess.call(command2.split(" "))
    command3 = 'setfacl -d -m u:{}:rwx {}'.format(username,data_path)
    subprocess.call(command3.split(" "))

    # Don't forget the BIL user and group!
    command4 = 'setfacl -m u:bil:rwx  {}'.format(data_path)
    subprocess.call(command4.split(" "))
    command5 = 'setfacl -m g:bil:rwx {}'.format(data_path)
    subprocess.call(command5.split(" "))
    command6 = 'setfacl -d -m u:bil:rwx {}'.format(data_path)
    subprocess.call(command6.split(" "))
    command7 = 'setfacl -d -m g:bil:rwx {}'.format(data_path)
    subprocess.call(command7.split(" "))

    #Finally create etc directory: 
    data_path2=data_path.replace("/lz/","/etc/")
    command44 = 'mkdir -p {}'.format(data_path2)
    subprocess.call(command44.split(" "))


@shared_task
def delete_data_path(host_and_path):
    """ We delete a staging area when we create a collection. """
    data_path = host_and_path.split(":")[1]
    command = 'rm -fr {}'.format(data_path)
    subprocess.call(command.split(" "))
    data_path2=data_path.replace("/lz/","/etc/")
    command2 = 'rm -fr {}'.format(data_path2)
    subprocess.call(command2.split(" "))


VALIDATION_PIPELINE_STEPS = [
    ("chown",                  ["sudo", "/bil/val/sbin/bil_lz_chown"]),
    ("find_empty_files",       ["/bil/val/bin/find_empty_files"]),
    ("fix_dirname_chars",      ["/bil/val/bin/fix_dirname_chars"]),
    ("fix_filename_chars",     ["/bil/val/bin/fix_filename_chars"]),
    ("make_and_submit_job_array", ["/bil/users/bil/generic/make_and_submit_job_array.sh"]),
]


def initial_pipeline_progress():
    """The starting state written to Collection.pipeline_progress before a run."""
    progress = {"_status": "running"}
    for step_name, _argv in VALIDATION_PIPELINE_STEPS:
        progress[step_name] = {"status": "pending"}
    return progress


def _save_progress(bil_uuid, progress):
    from .models import Collection
    Collection.objects.filter(bil_uuid=bil_uuid).update(pipeline_progress=progress)


@shared_task
def run_validation_pipeline(username, bil_uuid):
    """Run the five post-validation-request scripts against the collection's landing zone.

    Fail-fast: on the first non-zero exit, log a user_action_required event on the
    collection, email the admin, and stop. Task does not re-raise — failures are
    surfaced via EventsLog + email + Collection.pipeline_progress, not Celery task state.
    """
    data_path = "/bil/lz/{}/{}".format(username, bil_uuid)
    progress = initial_pipeline_progress()
    _save_progress(bil_uuid, progress)

    for step_name, argv in VALIDATION_PIPELINE_STEPS:
        progress[step_name] = {
            "status": "running",
            "started_at": timezone.now().isoformat(),
        }
        _save_progress(bil_uuid, progress)
        try:
            subprocess.run(argv + [data_path], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            progress[step_name] = {
                **progress[step_name],
                "status": "failed",
                "failed_at": timezone.now().isoformat(),
                "error": (exc.stderr or "").strip()[:1000],
            }
            progress["_status"] = "failed"
            _save_progress(bil_uuid, progress)
            _handle_pipeline_failure(username, bil_uuid, step_name, exc)
            return
        progress[step_name] = {
            **progress[step_name],
            "status": "done",
            "completed_at": timezone.now().isoformat(),
        }
        _save_progress(bil_uuid, progress)

    progress["_status"] = "done"
    _save_progress(bil_uuid, progress)


def _handle_pipeline_failure(username, bil_uuid, step_name, exc):
    from .models import Collection, EventsLog

    stderr = (exc.stderr or "").strip()
    notes = "[VALIDATION PIPELINE FAILED] step={} rc={} stderr={}".format(
        step_name, exc.returncode, stderr
    )[:256]

    coll = Collection.objects.filter(bil_uuid=bil_uuid).first()
    EventsLog.objects.create(
        collection_id=coll,
        project_id_id=(coll.project_id if coll else None),
        notes=notes,
        timestamp=timezone.now(),
        event_type="user_action_required",
    )

    subject = "[BIL Validations] Pipeline Failed: {}".format(bil_uuid)
    body = (
        "The post-validation-request pipeline failed for a submission.\n\n"
        "User: {user}\n"
        "BIL UUID: {uuid}\n"
        "Failed step: {step}\n"
        "Return code: {rc}\n"
        "Stderr:\n{stderr}\n"
    ).format(user=username, uuid=bil_uuid, step=step_name, rc=exc.returncode, stderr=stderr)
    send_mail(subject, body, VALIDATION_FAILURE_EMAIL_SENDER, [VALIDATION_FAILURE_EMAIL_RECIPIENT])

