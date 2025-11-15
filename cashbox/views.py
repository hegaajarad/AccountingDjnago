from decimal import Decimal
from django.views.generic import DetailView, ListView, CreateView, TemplateView
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, Case, When, F, DecimalField

from .models import Customer, CashBox, Transaction
from .forms import CashBoxForm, TransactionForm
from .pdf import render_to_pdf


class CustomerListView(ListView):
    model = Customer
    paginate_by = 20
    template_name = "cashbox/customer_list.html"


class CustomerCreateView(CreateView):
    model = Customer
    fields = ["name", "phone"]
    template_name = "cashbox/customer_form.html"
    success_url = reverse_lazy("customer_list")


class CustomerReportView(DetailView):
    model = Customer
    template_name = "cashbox/customer_report.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        customer = self.object
        cashboxes = customer.cashboxes.select_related("currency", "account_type")
        tx = (
            Transaction.objects.filter(cashbox__customer=customer)
            .values("cashbox__currency__code")
            .annotate(
                balance=Sum(
                    Case(
                        When(direction=Transaction.Direction.DEPOSIT, then=F("amount")),
                        When(direction=Transaction.Direction.WITHDRAW, then=-F("amount")),
                        output_field=DecimalField(max_digits=18, decimal_places=6),
                    )
                )
            )
        )
        per_currency = {row["cashbox__currency__code"]: row["balance"] for row in tx}
        total = sum((v or Decimal("0")) for v in per_currency.values())
        # Dashboard metrics for this customer
        transactions_count = Transaction.objects.filter(cashbox__customer=customer).count()
        cashboxes_count = cashboxes.count()
        currencies_count = cashboxes.values("currency_id").distinct().count()

        ctx.update(
            {
                "cashboxes": cashboxes,
                "per_currency": per_currency,
                "total": total,
                "transactions_count": transactions_count,
                "cashboxes_count": cashboxes_count,
                "currencies_count": currencies_count,
            }
        )
        return ctx


def customer_report_pdf(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    view = CustomerReportView()
    view.object = customer
    context = view.get_context_data(object=customer)
    context["customer"] = customer
    return render_to_pdf("cashbox/customer_report_pdf.html", context, filename=f"customer_{customer.id}.pdf")


def cashbox_transactions_pdf(request, pk):
    """Export full transaction report for a specific cash box as PDF."""
    cashbox = get_object_or_404(
        CashBox.objects.select_related("customer", "currency", "account_type"), pk=pk
    )
    transactions = (
        Transaction.objects.filter(cashbox=cashbox)
        .select_related(
            "cashbox",
            "cashbox__customer",
            "cashbox__currency",
            "cashbox__account_type",
        )
        .order_by("-created_at", "-id")
    )
    context = {
        "cashbox": cashbox,
        "customer": cashbox.customer,
        "transactions": transactions,
        "title": _("Transactions for Cash Box"),
    }
    # Build descriptive filename: CustomerName_CashBoxName_Date.pdf
    from django.utils import timezone
    import re

    def sanitize(name: str) -> str:
        # Replace whitespace with underscores and strip unsafe characters, keep unicode letters/numbers
        name = re.sub(r"\s+", "_", name or "")
        # Remove characters problematic for files: / \ : * ? " < > |
        return re.sub(r"[\\/:*?\"<>|]", "", name).strip("._") or "Unnamed"

    cust_part = sanitize(cashbox.customer.name)
    # Use cashbox.name if set, else fallback to CUR-ACCT
    box_label = cashbox.name if cashbox.name else f"{cashbox.currency.code}-{cashbox.account_type.code}"
    box_part = sanitize(box_label)
    date_part = timezone.now().strftime("%Y%m%d_%H%M")
    filename = f"{cust_part}_{box_part}_{date_part}.pdf"
    return render_to_pdf("cashbox/cashbox_transactions_pdf.html", context, filename=filename)


class CashBoxCreateView(CreateView):
    model = CashBox
    form_class = CashBoxForm
    template_name = "cashbox/cashbox_form.html"

    def get_success_url(self):
        # redirect to customer report
        return reverse_lazy("customer_report", kwargs={"pk": self.object.customer.pk})


class TransactionCreateView(CreateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "cashbox/transaction_form.html"

    def get_initial(self):
        initial = super().get_initial()
        cashbox_id = self.request.GET.get("cashbox")
        if cashbox_id:
            initial["cashbox"] = cashbox_id
        return initial

    def get_success_url(self):
        # redirect to customer report
        return reverse_lazy(
            "customer_report", kwargs={"pk": self.object.cashbox.customer.pk}
        )



class DashboardView(TemplateView):
    template_name = "cashbox/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            {
                "customers_count": Customer.objects.count(),
                "transactions_count": Transaction.objects.count(),
                "cashboxes_count": CashBox.objects.count(),
                # These imports are local to avoid circulars if models expand later
                "currencies_count": self._count("Currency"),
                "account_types_count": self._count("AccountType"),
            }
        )
        return ctx

    def _count(self, model_name: str) -> int:
        # small helper to fetch model by name without importing here
        from django.apps import apps

        Model = apps.get_model("cashbox", model_name)
        return Model.objects.count()


class CustomerTransactionsView(ListView):
    model = Transaction
    paginate_by = 50
    template_name = "cashbox/transactions_list.html"

    def get_queryset(self):
        self.customer = get_object_or_404(Customer, pk=self.kwargs["pk"])
        qs = (
            Transaction.objects.filter(cashbox__customer=self.customer)
            .select_related(
                "cashbox",
                "cashbox__customer",
                "cashbox__currency",
                "cashbox__account_type",
            )
            .order_by("-created_at", "-id")
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            {
                "scope": "customer",
                "customer": self.customer,
                "title": _("Transactions for %(name)s") % {"name": self.customer.name},
            }
        )
        return ctx


class CashBoxTransactionsView(ListView):
    model = Transaction
    paginate_by = 50
    template_name = "cashbox/transactions_list.html"

    def get_queryset(self):
        self.cashbox = get_object_or_404(
            CashBox.objects.select_related("customer", "currency", "account_type"),
            pk=self.kwargs["pk"],
        )
        qs = (
            Transaction.objects.filter(cashbox=self.cashbox)
            .select_related(
                "cashbox",
                "cashbox__customer",
                "cashbox__currency",
                "cashbox__account_type",
            )
            .order_by("-created_at", "-id")
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            {
                "scope": "cashbox",
                "cashbox": self.cashbox,
                "customer": self.cashbox.customer,
                "title": _("Transactions for Cash Box"),
            }
        )
        return ctx


class TransactionReviewListView(ListView):
    model = Transaction
    paginate_by = 50
    template_name = "cashbox/transactions_list.html"

    def get_queryset(self):
        qs = (
            Transaction.objects.all()
            .select_related(
                "cashbox",
                "cashbox__customer",
                "cashbox__currency",
                "cashbox__account_type",
            )
            .order_by("-created_at", "-id")
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({"scope": "all", "title": _("All Transactions")})
        return ctx
