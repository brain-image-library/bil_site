import requests
from collections import namedtuple

from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from django.utils.html import format_html

from .models import BIL_ID, Collection, EventsLog

DashboardTable = namedtuple("DashboardTable", ["headers", "rows"])

_CURATOR_SECTIONS = {
    "Passed Validation": "ASANA_GID_PASSED_VALIDATION",
    "In Curation": "ASANA_GID_IN_CURATION",
    "Curation Issue": "ASANA_GID_CURATION_ISSUE",
}
_CACHE_KEY = "dashboard_asana_curator_queue"
_CACHE_TTL = 60


def fetch_asana_curator_queue():
    """Return {section_name: [bil_uuid, ...]} from Asana, cached for 60s."""
    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return cached

    token = getattr(settings, "ASANA_PAT", "")
    headers = {"Authorization": f"Bearer {token}"}
    result = {}

    for section_name, setting_key in _CURATOR_SECTIONS.items():
        gid = getattr(settings, setting_key, "")
        if not gid:
            result[section_name] = []
            continue
        url = f"https://app.asana.com/api/1.0/sections/{gid}/tasks"
        resp = requests.get(url, headers=headers, params={"opt_fields": "name"}, timeout=10)
        resp.raise_for_status()
        result[section_name] = [t["name"].split()[0] for t in resp.json().get("data", [])]

    cache.set(_CACHE_KEY, result, _CACHE_TTL)
    return result


def _build_curator_sections(tasks_by_section):
    """Return list of (section_name, DashboardTable) — one table per section."""
    all_uuids = [uuid for uuids in tasks_by_section.values() for uuid in uuids]
    collections_by_uuid = {
        c.bil_uuid: c for c in Collection.objects.filter(bil_uuid__in=all_uuids)
    }
    sections = []
    for section_name, uuids in tasks_by_section.items():
        rows = []
        for uuid in uuids:
            coll = collections_by_uuid.get(uuid)
            if coll:
                admin_url = reverse("admin:ingest_collection_change", args=[coll.pk])
                action = format_html('<a href="{}">Edit &#8594;</a>', admin_url)
            else:
                action = "-"
            rows.append([uuid, action])
        sections.append((section_name, DashboardTable(
            headers=["UUID", ""],
            rows=rows,
        )))
    return sections


def fetch_pipeline_counters(tasks_by_section):
    """Return ordered list of (label, count) for the pipeline stat row.

    Curator-side sections (Passed Validation, In Curation, Curation Issue)
    use counts from the already-fetched Asana data. DB-derivable states use
    Collection queryset counts.
    """
    return [
        ("Validation Running", Collection.objects.filter(submission_status="PENDING").count()),
        ("Failed Validation", Collection.objects.filter(submission_status="FAILED").count()),
        ("Passed Validation", len(tasks_by_section.get("Passed Validation", []))),
        ("In Curation", len(tasks_by_section.get("In Curation", []))),
        ("Curation Issue", len(tasks_by_section.get("Curation Issue", []))),
        ("Public", Collection.objects.filter(submission_status="SUCCESS", validation_status="SUCCESS").count()),
    ]


def fetch_doi_queue():
    qs = (
        BIL_ID.objects.filter(
            doi=False,
            v2_ds_id__sheet__collection__submission_status="SUCCESS",
            v2_ds_id__sheet__collection__validation_status="SUCCESS",
        )
        .select_related("v2_ds_id__sheet__collection")[:50]
    )
    rows = []
    for bil_id in qs:
        ds = bil_id.v2_ds_id
        coll = ds.sheet.collection if ds and ds.sheet else None
        admin_url = reverse("admin:ingest_bil_id_change", args=[bil_id.pk])
        rows.append([
            bil_id.bil_id or "-",
            ds.bildirectory if ds else "-",
            coll.name if coll else "-",
            format_html('<a href="{}">Create DOI →</a>', admin_url),
        ])
    return DashboardTable(
        headers=["BIL ID", "Directory", "Collection", ""],
        rows=rows,
    )


def fetch_recent_events():
    qs = EventsLog.objects.select_related("collection_id").order_by("-timestamp")[:15]
    rows = []
    for event in qs:
        coll = event.collection_id
        if coll:
            admin_url = reverse("admin:ingest_collection_change", args=[coll.pk])
            uuid_cell = format_html('<a href="{}">{}</a>', admin_url, coll.bil_uuid)
        else:
            uuid_cell = "-"
        rows.append([
            event.timestamp.strftime("%Y-%m-%d %H:%M"),
            event.get_event_type_display(),
            uuid_cell,
        ])
    return DashboardTable(
        headers=["Timestamp", "Event", "Collection"],
        rows=rows,
    )


def dashboard_callback(request, context):
    """UNFOLD dashboard callback — populates context for the admin dashboard."""
    try:
        tasks_by_section = fetch_asana_curator_queue()
        curator_sections = _build_curator_sections(tasks_by_section)
        asana_error = None
    except Exception as exc:
        curator_sections = []
        tasks_by_section = {}
        asana_error = str(exc)

    context.update({
        "curator_sections": curator_sections,
        "asana_error": asana_error,
        "pipeline_counters": fetch_pipeline_counters(tasks_by_section),
        "doi_table": fetch_doi_queue(),
        "event_table": fetch_recent_events(),
    })
    return context
