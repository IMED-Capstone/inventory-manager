from django import forms


class ExcelUploadForm(forms.Form):
    """Used in the admin panel for uploading an Excel file containing transaction data."""
    excel_file = forms.FileField(label="Upload Excel File")

class AddRemoveItemsByBarcodeForm(forms.Form):
    barcode = forms.CharField()
    add_remove = forms.ChoiceField(
        choices=[('add', 'Add Items'), ('remove', 'Remove Items')],
        widget=forms.RadioSelect(attrs={'class': 'btn-check', 'autocomplete': 'off'}),
        initial='add',
    )