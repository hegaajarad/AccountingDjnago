from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import CheckConstraint, Q, F, Sum, Case, When, Index, DecimalField


class Customer(models.Model):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover - simple repr
        return self.name


class Currency(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=10, blank=True)
    decimal_places = models.PositiveSmallIntegerField(default=2)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:  # pragma: no cover - simple repr
        return f"{self.code}"


class AccountType(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=50)

    def __str__(self) -> str:  # pragma: no cover - simple repr
        return self.name


class CashBox(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="cashboxes")
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    account_type = models.ForeignKey(AccountType, on_delete=models.PROTECT)
    # Optional friendly name set by user for easier identification
    name = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            Index(fields=["customer", "currency", "account_type"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - simple repr
        base = f"{self.customer} - {self.currency.code} - {self.account_type.code}"
        return f"{base} ({self.name})" if self.name else base

    @property
    def balance(self) -> Decimal:
        signed_sum = self.transactions.aggregate(
            total=Sum(
                Case(
                    When(direction=Transaction.Direction.DEPOSIT, then=F("amount")),
                    When(direction=Transaction.Direction.WITHDRAW, then=-F("amount")),
                    default=Decimal("0.0"),
                    output_field=DecimalField(max_digits=18, decimal_places=6),
                )
            )
        )["total"]
        return signed_sum or Decimal("0")


class Transaction(models.Model):
    class Direction(models.TextChoices):
        DEPOSIT = "DEPOSIT", "Deposit"
        WITHDRAW = "WITHDRAW", "Withdraw"

    cashbox = models.ForeignKey(CashBox, on_delete=models.CASCADE, related_name="transactions")
    direction = models.CharField(max_length=8, choices=Direction.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=6)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            Index(fields=["cashbox", "created_at"]),
        ]
        constraints = [
            CheckConstraint(check=Q(amount__gt=0), name="amount_positive"),
        ]

    def clean(self):
        # Enforce currency-specific decimal places
        if not self.cashbox_id:
            return
        dp = self.cashbox.currency.decimal_places
        quant = Decimal(1).scaleb(-dp)
        try:
            self.amount = self.amount.quantize(quant, rounding=ROUND_HALF_UP)
        except Exception as _e:  # pragma: no cover - defensive
            raise ValidationError({"amount": f"Invalid amount precision for {self.cashbox.currency.code}"})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
