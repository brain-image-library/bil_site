# The order that these fields appear in this list will affect the order that
# they appear on the Metadata Creation page
#
metadata_fields = [
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

collection_fields = [
    'name',
    'description',
    'organization_name',
    'lab_name',
    'project_funder',
    'project_funder_id',
]


# this is *user-supplied* metadata, although we omit the associated collection,
# since we grab that through other means.
required_metadata = [
    'sample_id',
    'organism_type',
    'organism_ncbi_taxonomy_id',
    'transgenetic_line_information',
    'modality',
    'method',
    'technique',
    'anatomical_structure',
    'total_processed_cells',
    'organization',
    'lab',
    'investigator',
    'grant_number',
    'r24_name',
    'r24_directory',
]
modalities = [
    'anatomy',
    'cell morphology',
    'connectivity',
    'electrophysiology',
    'epigenomics'
    'histology imaging',
    'multimodal',
    'optical physiology',
    'population imaging',
    'spatial transcriptomics',
]
techniques = [
    'technique_name',
    'anterograde tracing',
    'calcium imaging',
    'cre-dependent',
    'FISH',
    'fMOST',
    'histology',
    'in situ hybridization',
    'mC-seq2',
    'MERFISH',
    'MORF genetic sparse labeling',
    'mouselight',
    'multi electrode extracellular electrophysiology technique',
    'neuron morphology reconstruction',
    'patch-seq',
    'retrograde tracing',
    'retrograde transsynaptic tracing',
    'seqFISH',
    'STPT',
    'TRIO tracing',
    'light sheet microscopy',
    'OCT',
    'whole cell patch clamp',
    'VISor',
    'CISI',
    'enhancer virus labeling',
]
