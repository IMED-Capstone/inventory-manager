"""Provides custom filters used for views across the project."""

import re
from django import template

register = template.Library()

@register.filter
def lower(value:str) -> str:
    """
    Converts a string into lowercase.
    Used to provide lowercase text in Django template syntax in various views.

    Args:
        value (str): input string to convert

    Returns:
        str: output string in lowercase representation
    """
    return value.lower()

@register.filter
def camel_to_words(value: str) -> str:
    """
    Converts a camel_case string into words separated by spaces (Camel Case).
    Used to provide string manipulation of text in various views (e.g. homepage for displaying model names nicely in respective cards).

    Args:
        value (str): input string to manipulate in camel_case

    Returns:
        str: output string as capital words separated by spaces (e.g. Camel Case)
    """
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', value)