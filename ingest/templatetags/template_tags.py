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

# Ensure to register your filter
register.filter('pretty_print', pretty_print)
