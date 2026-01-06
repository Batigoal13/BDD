from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Permet d'accéder à un élément d'un dictionnaire dans un template Django.
    Usage: {{ dict|get_item:key }}
    """
    if dictionary and key:
        return dictionary.get(key)
    return None
