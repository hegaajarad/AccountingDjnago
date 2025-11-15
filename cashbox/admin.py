from django.contrib import admin
from .models import Customer, Currency, AccountType, CashBox, Transaction


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "created_at")
    search_fields = ("name", "phone")


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "decimal_places", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(AccountType)
class AccountTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(CashBox)
class CashBoxAdmin(admin.ModelAdmin):
    list_display = ("customer", "currency", "account_type", "name", "created_at")
    list_filter = ("currency", "account_type")
    search_fields = ("customer__name",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("cashbox", "direction", "amount", "created_at")
    list_filter = ("direction", "cashbox__currency")
    search_fields = ("cashbox__customer__name", "note")
