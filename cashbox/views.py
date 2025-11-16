from decimal import Decimal
from django.views.generic import DetailView, ListView, CreateView, TemplateView
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, Case, When, F, DecimalField

from .models import Customer, CashBox, Transaction
from .forms import CashBoxForm, TransactionForm
from .pdf import render_to_pdf


class CustomerListView(LoginRequiredMixin, ListView):
    model = Customer
    paginate_by = 20
    template_name = "cashbox/customer_list.html"


class CustomerCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "cashbox.add_customer"
    model = Customer
    fields = ["name", "phone"]
    template_name = "cashbox/customer_form.html"
    success_url = reverse_lazy("customer_list")


class CustomerReportView(LoginRequiredMixin, DetailView):
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


@login_required
def customer_report_pdf(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    view = CustomerReportView()
    view.object = customer
    context = view.get_context_data(object=customer)
    context["customer"] = customer
    return render_to_pdf("cashbox/customer_report_pdf.html", context, filename=f"customer_{customer.id}.pdf")


@login_required
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


class CashBoxCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "cashbox.add_cashbox"
    model = CashBox
    form_class = CashBoxForm
    template_name = "cashbox/cashbox_form.html"

    def get_success_url(self):
        # redirect to customer report
        return reverse_lazy("customer_report", kwargs={"pk": self.object.customer.pk})


class TransactionCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "cashbox.add_transaction"
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
        # After creating a transaction, show a small success/summary page
        return reverse_lazy("transaction_success", kwargs={"pk": self.object.pk})


class TransactionSuccessView(LoginRequiredMixin, DetailView):
    model = Transaction
    template_name = "cashbox/transaction_success.html"



class DashboardView(LoginRequiredMixin, TemplateView):
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


@login_required
def transaction_search(request):
    """Search by Transaction ID and redirect to its info page.

    Accepts numeric IDs with or without leading zeros (e.g., 000123 or 123).
    If the transaction doesn't exist or the input is invalid, redirect back to
    the dashboard with a small flag to show an error message.
    """
    q = (request.GET.get("q") or "").strip()
    if not q:
        return redirect("dashboard")

    # Extract digits to allow inputs like "#000123" or "TX-000123"
    import re

    m = re.search(r"(\d+)", q)
    if not m:
        return redirect(f"{reverse('dashboard')}?tx_not_found=1")

    try:
        pk = int(m.group(1))
    except Exception:
        return redirect(f"{reverse('dashboard')}?tx_not_found=1")

    try:
        Transaction.objects.get(pk=pk)
    except Transaction.DoesNotExist:
        return redirect(f"{reverse('dashboard')}?tx_not_found=1")

    return redirect("transaction_success", pk=pk)


class CustomerTransactionsView(LoginRequiredMixin, ListView):
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


class CashBoxTransactionsView(LoginRequiredMixin, ListView):
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


class TransactionReviewListView(LoginRequiredMixin, ListView):
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


# --- ReportLab Arabic PDF demo ---
@login_required
def generate_pdf(request):
    """Generate a small PDF using ReportLab with proper Arabic shaping and RTL.

    This registers an Arabic-capable TTF from static/fonts/Amiri-Regular.ttf
    (you can replace with Cairo/Noto Naskh/Tajawal), reshapes the Arabic text
    using arabic-reshaper and reorders it using python-bidi, then renders it
    with ReportLab.
    """
    # Lazy imports to avoid forcing these deps during non-PDF views
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    import arabic_reshaper
    from bidi.algorithm import get_display

    # 1) Register Arabic font (expects file at static/fonts/Amiri-Regular.ttf)
    # Using relative path from project root where STATICFILES_DIRS points to "static"
    font_name = "Amiri"
    font_path = "static/fonts/Amiri-Regular.ttf"
    try:
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, font_path))
        use_font = font_name
    except Exception:
        # Fallback to a safe font if registration fails (text may not shape)
        use_font = "Helvetica"

    # 2) Your Arabic text
    text = "مرحباً بك في نظام بريميكس للحسابات"

    # 3) Apply shaping and RTL reordering
    reshaped = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped)

    # 4) Build PDF response
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="test.pdf"'

    c = rl_canvas.Canvas(response)

    # 5) Draw text using the registered Arabic font, right-aligned
    try:
        c.setFont(use_font, 18)
    except Exception:
        # In the unlikely event font size setting fails, ignore
        pass
    # A4 width ~ 595 points; draw near the right edge with RTL-appropriate call
    c.drawRightString(550, 800, bidi_text)

    c.showPage()
    c.save()

    return response
