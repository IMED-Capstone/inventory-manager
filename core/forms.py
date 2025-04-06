from django import forms


class ExcelUploadForm(forms.Form):
    """Used in the admin panel for uploading an Excel file containing transaction data."""
    excel_file = forms.FileField(label="Upload Excel File")

