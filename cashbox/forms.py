from django import forms
from .models import CashBox, Transaction


class CashBoxForm(forms.ModelForm):
    class Meta:
        model = CashBox
        fields = ["customer", "currency", "account_type", "name"]


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["cashbox", "direction", "amount", "note"]
