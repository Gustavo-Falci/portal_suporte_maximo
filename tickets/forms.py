from django.contrib.auth.forms import AuthenticationForm
from django import forms

class EmailAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="E-mail",
        max_length=254,
        widget=forms.EmailInput(attrs={"autofocus": True})
    )