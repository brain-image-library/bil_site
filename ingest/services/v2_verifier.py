from ingest.models import BIL_ID, Dataset, Sheet


def check_directory_match(collection) -> list:
    """ORM equivalent of check_ids.py directory_mismatch_check.

    Returns list of dicts with keys:
    bil_id, v2_ds_id, dataset_directory, v1_ds_id, metadata_directory, status
    """
    latest_sheet = (
        Sheet.objects.filter(collection=collection)
        .order_by('-date_uploaded')
        .first()
    )
    if not latest_sheet:
        return []

    bil_ids = (
        BIL_ID.objects
        .filter(v2_ds_id__sheet=latest_sheet, v2_ds_id__isnull=False)
        .select_related('v2_ds_id', 'v1_ds_id')
    )

    results = []
    for b in bil_ids:
        ds = b.v2_ds_id
        dm = b.v1_ds_id
        ds_dir = ds.bildirectory if ds else ''
        dm_dir = dm.r24_directory if dm else ''
        # When v1_ds_id (dm) is None, status must be 'MISMATCH' regardless of directory values
        if dm is None:
            status = 'MISMATCH'
        else:
            status = 'MATCH' if ds_dir == dm_dir else 'MISMATCH'
        results.append({
            'bil_id': b.bil_id,
            'v2_ds_id': ds.id if ds else None,
            'dataset_directory': ds_dir,
            'v1_ds_id': dm.id if dm else None,
            'metadata_directory': dm_dir,
            'status': status,
        })
    return results


def get_bil_id_summary(collection) -> list:
    """Dataset <-> BIL ID summary for the latest sheet on this collection.

    Returns list of dicts with keys: dataset_id, dataset_title, bil_id
    """
    latest_sheet = (
        Sheet.objects.filter(collection=collection)
        .order_by('-date_uploaded')
        .first()
    )
    if not latest_sheet:
        return []

    datasets = Dataset.objects.filter(sheet=latest_sheet)
    results = []
    for ds in datasets:
        bil = BIL_ID.objects.filter(v2_ds_id=ds).first()
        results.append({
            'dataset_id': ds.id,
            'dataset_title': ds.title,
            'bil_id': bil.bil_id if bil else None,
        })
    return results
