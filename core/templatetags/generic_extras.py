from django import template

register = template.Library()

@register.filter
def lower(value:str):
    return value.lower()