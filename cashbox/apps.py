from django.apps import AppConfig


def _ensure_default_groups():
    """Create default groups with appropriate permissions.

    - Viewers: can view models only
    - Editors: can add/change/delete models
    This runs on app ready; safe if DB tables exist.
    """
    try:
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType
        from .models import Customer, CashBox, Transaction

        models = [Customer, CashBox, Transaction]
        # Collect permissions
        view_perms = []
        edit_perms = []
        for model in models:
            ct = ContentType.objects.get_for_model(model)
            # Django default codenames
            for codename in ("view_{}", "add_{}", "change_{}", "delete_{}"):  # template
                pass
            # Fetch and group
            view = Permission.objects.filter(content_type=ct, codename=f"view_{model._meta.model_name}")
            add = Permission.objects.filter(content_type=ct, codename=f"add_{model._meta.model_name}")
            chg = Permission.objects.filter(content_type=ct, codename=f"change_{model._meta.model_name}")
            dele = Permission.objects.filter(content_type=ct, codename=f"delete_{model._meta.model_name}")
            view_perms.extend(list(view))
            edit_perms.extend(list(add) + list(chg) + list(dele))

        viewers, _ = Group.objects.get_or_create(name="Viewers")
        editors, _ = Group.objects.get_or_create(name="Editors")
        viewers.permissions.set(view_perms)
        editors.permissions.set(view_perms + edit_perms)
    except Exception:
        # Silently ignore during migrations or before tables exist
        return


class CashboxConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "cashbox"

    def ready(self):  # pragma: no cover - side-effect setup
        _ensure_default_groups()
