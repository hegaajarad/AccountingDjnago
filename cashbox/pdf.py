from django.template.loader import get_template
from django.http import HttpResponse
from django.utils import translation
from xhtml2pdf import pisa
import io


def render_to_pdf(template_src, context_dict=None, filename="report.pdf"):
    # Ensure language context is available in PDF templates
    lang = translation.get_language() or "en"
    ctx = dict(context_dict or {})
    ctx.setdefault("LANGUAGE_CODE", lang)
    ctx.setdefault("is_rtl", lang.startswith("ar"))

    # Note: Avoid overriding xhtml2pdf global defaults here to prevent
    # compatibility issues across versions. Arabic/RTL support is handled
    # via template CSS and the injected is_rtl flag.

    template = get_template(template_src)
    html = template.render(ctx)
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), dest=result, encoding="UTF-8")
    if not pdf.err:
        resp = HttpResponse(result.getvalue(), content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp
    return HttpResponse("Error generating PDF", status=500)
