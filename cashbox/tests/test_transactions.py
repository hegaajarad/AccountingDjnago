from decimal import Decimal
from django.test import TestCase
from django.urls import reverse

from cashbox.models import Customer, Currency, AccountType, CashBox, Transaction


class TransactionTests(TestCase):
    def setUp(self):
        self.cust = Customer.objects.create(name="Ali", phone="123")
        self.usd = Currency.objects.create(code="USD", name="US Dollar", decimal_places=2)
        self.cash = AccountType.objects.create(code="CASH", name="USD Cash")
        self.box = CashBox.objects.create(customer=self.cust, currency=self.usd, account_type=self.cash)

    def test_deposit_withdraw_balance(self):
        Transaction.objects.create(cashbox=self.box, direction=Transaction.Direction.DEPOSIT, amount=Decimal("100"))
        Transaction.objects.create(cashbox=self.box, direction=Transaction.Direction.WITHDRAW, amount=Decimal("40"))
        self.assertEqual(self.box.balance, Decimal("60.00"))

    def test_negative_balance_allowed(self):
        Transaction.objects.create(cashbox=self.box, direction=Transaction.Direction.WITHDRAW, amount=Decimal("10"))
        self.assertEqual(self.box.balance, Decimal("-10.00"))

    def test_quantization_enforced(self):
        t = Transaction(cashbox=self.box, direction=Transaction.Direction.DEPOSIT, amount=Decimal("12.3456"))
        t.save()
        self.assertEqual(t.amount, Decimal("12.35"))


class PdfTests(TestCase):
    def setUp(self):
        self.cust = Customer.objects.create(name="Sara", phone="555")
        self.usd = Currency.objects.create(code="USD", name="US Dollar", decimal_places=2)
        self.cash = AccountType.objects.create(code="CASH", name="USD Cash")
        self.box = CashBox.objects.create(customer=self.cust, currency=self.usd, account_type=self.cash)

    def test_customer_report_pdf(self):
        url = reverse("customer_report_pdf", args=[self.cust.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

    def test_cashbox_transactions_pdf(self):
        # Create some transactions to include in the report
        Transaction.objects.create(cashbox=self.box, direction=Transaction.Direction.DEPOSIT, amount=Decimal("25"))
        url = reverse("cashbox_transactions_pdf", args=[self.box.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
