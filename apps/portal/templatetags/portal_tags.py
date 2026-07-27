from django import template

register = template.Library()

@register.filter(name='dict_get')
def dict_get(value, arg):
    """
    Returns the dictionary value for the given key.
    Usage: {{ my_dict|dict_get:key_name }}
    """
    if isinstance(value, dict):
        return value.get(arg)
    return None
