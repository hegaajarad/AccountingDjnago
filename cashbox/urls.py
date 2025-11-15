from django.urls import path
from .views import (
    DashboardView,
    CustomerListView,
    CustomerCreateView,
    CustomerReportView,
    customer_report_pdf,
    CashBoxCreateView,
    TransactionCreateView,
    CustomerTransactionsView,
    CashBoxTransactionsView,
    TransactionReviewListView,
    cashbox_transactions_pdf,
)

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("customers/", CustomerListView.as_view(), name="customer_list"),
    path("customers/new/", CustomerCreateView.as_view(), name="customer_create"),
    path("customers/<int:pk>/", CustomerReportView.as_view(), name="customer_report"),
    path("customers/<int:pk>/transactions/", CustomerTransactionsView.as_view(), name="customer_transactions"),
    path("customers/<int:pk>/pdf/", customer_report_pdf, name="customer_report_pdf"),
    path("cashboxes/new/", CashBoxCreateView.as_view(), name="cashbox_create"),
    path("cashboxes/<int:pk>/transactions/", CashBoxTransactionsView.as_view(), name="cashbox_transactions"),
    path("cashboxes/<int:pk>/transactions/pdf/", cashbox_transactions_pdf, name="cashbox_transactions_pdf"),
    path("transactions/new/", TransactionCreateView.as_view(), name="transaction_create"),
    path("transactions/", TransactionReviewListView.as_view(), name="transaction_review"),
]
