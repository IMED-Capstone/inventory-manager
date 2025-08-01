from django import forms
from django.core.validators import MinValueValidator


class ExcelUploadForm(forms.Form):
    """Used in the admin panel for uploading an Excel file containing transaction data."""
    excel_file = forms.FileField(label="Upload Excel File")

class AddRemoveItemsByBarcodeForm(forms.Form):
    barcode = forms.CharField(widget=forms.TextInput(attrs={'disabled': 'disabled'}))
    add_remove = forms.ChoiceField(
        choices=[('in', 'Add Items'), ('out', 'Remove Items')],
        widget=forms.RadioSelect(attrs={'class': 'btn-check', 'autocomplete': 'off'}),
        initial='in',
    )
    item_quantity = forms.IntegerField(
        validators=[MinValueValidator(1)],
        widget=forms.NumberInput(attrs={
            'min': 1,
            'class': 'form-control',
        }),
        initial=1,
        required=True
    )