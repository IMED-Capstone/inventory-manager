from django import forms


class ExcelUploadForm(forms.Form):
    """Used in the admin panel for uploading an Excel file containing transaction data."""
    excel_file = forms.FileField(label="Upload Excel File")

class UDI_Form(forms.Form):
    """Used in the admin panel for uploading an UDI containing item data."""
    udi_input = forms.CharField(max_length = 200)