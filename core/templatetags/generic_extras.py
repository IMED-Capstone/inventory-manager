import re
from django import template

register = template.Library()

@register.filter
def lower(value:str):
    return value.lower()

@register.filter
def camel_to_words(value: str):
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', value)