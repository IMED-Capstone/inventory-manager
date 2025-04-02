from django import forms

class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField(label="Upload Excel File")

class DateRangeForm(forms.Form):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Start Date"
    )

    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="End Date"
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if (start_date and end_date) and (start_date > end_date):
            raise forms.ValidationError("End date must be after start date.")
        
        return cleaned_data
