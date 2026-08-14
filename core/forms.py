"""Defines forms used across the `Core` app."""

from django import forms
from django.utils import timezone


class ExcelUploadForm(forms.Form):
    """Used in the admin panel for uploading an Excel file containing transaction data."""

    excel_file = forms.FileField(label="Upload Excel File")

class UDI_Form(forms.Form):
    """Used in the admin panel for uploading an UDI containing item data using a barcode."""
    udi_input = forms.CharField(max_length = 200, label="Scan UDI barcode or manually enter a UDI")

class AddRemoveItemsByBarcodeForm(forms.Form):
    """
    A form used to add or remove :class:`Items <core.models.Item>` by a barcode-provided unique ID.
    Supports add and remove mode options, as defined by `add_remove`.
    Each UDI identifies one physical item, so every submission changes exactly one item.
    """

    barcode = forms.CharField()
    add_remove = forms.ChoiceField(
        choices=[("in", "Add Items"), ("out", "Remove Items")],
        widget=forms.RadioSelect(attrs={"class": "btn-check", "autocomplete": "off"}),
        initial="in",
    )
    is_waste = forms.BooleanField(required=False)
    occurred_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"},
            format="%Y-%m-%dT%H:%M",
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
    )
    estimated_cost = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=14,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={"min": 0, "step": "0.01", "class": "form-control"}
        ),
        help_text="Optional estimated cost in USD.",
    )

    def clean(self):
        cleaned_data = super().clean()
        is_waste = cleaned_data.get("is_waste", False)
        add_remove = cleaned_data.get("add_remove")

        if is_waste and add_remove != "out":
            self.add_error("is_waste", "Only removed items can be recorded as waste.")

        if is_waste and cleaned_data.get("occurred_at") is None:
            cleaned_data["occurred_at"] = timezone.now()

        if not is_waste:
            cleaned_data["notes"] = ""
            cleaned_data["estimated_cost"] = None

        return cleaned_data


class WasteReversalRequestForm(forms.Form):
    reason = forms.CharField(
        required=False,
        label="Correction reason",
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
    )
