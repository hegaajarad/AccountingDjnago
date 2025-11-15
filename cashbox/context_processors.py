from .models import Customer


def nav_customers(request):
    """Provide customers for navbar dropdown.

    Keep it lightweight by only selecting id and name, ordered by name.
    """
    customers = Customer.objects.all().only("id", "name").order_by("name")
    return {"nav_customers": customers}
