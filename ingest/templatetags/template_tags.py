from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()

@register.filter(name='pretty_print')
def pretty_print(value):
    # Convert the JSON object to a Python dictionary if it's not already.
    if isinstance(value, str):
        value = json.loads(value)
    
    try:
        category = value.get('category', 'No category')
        record = value.get('record', {})
        # Initialize the HTML string with category and study_id.
        html_string = f'Category: <strong>{category}</strong>'
        
        # Iterate over the key-value pairs in the record dictionary.
        for key, val in record.items():
            # Skip key-value pairs where the value is 'None'.
            if val is not None:
                html_string += f'<br>{key.capitalize().replace("_", " ")}: <strong>{val}</strong>'
        
        # Check for and append 'Has Parent' if it exists.
        edges = value.get('edges', {})
        has_parent = edges.get('has_parent', [])
        if has_parent:
            # Assume has_parent is a list and join multiple values with a comma.
            parents = ', '.join(has_parent)
            html_string += f'<br>Has Parent Identifier: <strong>{parents}<strong/>'

        return mark_safe(html_string)
    except (ValueError, TypeError):
        return 'Invalid data'

@register.filter(name='human_key')
def human_key(value):
    return str(value).replace('_', ' ').title()

@register.filter(name='nhash_prefix')
def nhash_prefix(value):
    return str(value)[:2].lower()

@register.filter(name='is_empty_val')
def is_empty_val(value):
    """True when a value should be treated as blank: None, '', {}, []."""
    if value is None:
        return True
    if isinstance(value, (dict, list)):
        return len(value) == 0
    return str(value).strip() == ''

# Ensure to register your filter
register.filter('pretty_print', pretty_print)
register.filter('human_key', human_key)
register.filter('nhash_prefix', nhash_prefix)
register.filter('is_empty_val', is_empty_val)
