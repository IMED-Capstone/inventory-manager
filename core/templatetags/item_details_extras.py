"""Provides custom filters for the `ItemDetails` view."""

from django import template

register = template.Library()

@register.filter
def get_field_value(obj, field_name):
    """
    Used to get the value of a field (`field_name`) from an `Item` model in the ItemDetails view.

    Args:
        obj (_type_): The `Item` model instance
        field_name (_type_): The field name for which to get the corresponding value

    Returns:
        _type_: The value of the `Item`'s field, as specified by `field_name`.
    """
    return getattr(obj, field_name, '')