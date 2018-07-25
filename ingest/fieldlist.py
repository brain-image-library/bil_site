# The order that these fields appear in this list will affect the order that
# they appear on the Metadata Creation page
#
# XXX: rename this. it's too generic.
attrs = [
    'collection',
    'project_name',
    'project_description',
    'background_strain',
    'taxonomy_name',
    'transgenic_line_name',
    'age',
    'age_unit',
    'sex',
    'organ',
    'organ_substructure',
    'assay',
    'slicing_direction',
    'image_map_style',
    'processing_level',
    'image_filename_pattern',
    'directory',
]

# this is *user-supplied* metadata, although we omit the associated collection,
# since we grab that through other means.
required_metadata = [
    'project_name',
    'project_description',
    'background_strain',
    'age_unit',
    'sex',
    'slicing_direction',
    'image_map_style',
    'processing_level',
    'image_filename_pattern',
    'directory',
]
