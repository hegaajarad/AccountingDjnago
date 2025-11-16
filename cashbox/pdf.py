from django.template.loader import get_template
from django.http import HttpResponse
from django.utils import translation
from django.conf import settings
from xhtml2pdf import pisa
import io
import re
from urllib.parse import quote
import os

# ReportLab font registration for Arabic-capable fonts
#
# Note: You can place an Arabic-capable TTF in your project at:
#   <project>/static/fonts/Amiri-Regular.ttf  (or Cairo/NotoNaskhArabic/Tajawal)
# This module will automatically pick it up and register it for PDF output.
try:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except Exception:  # pragma: no cover - safety if reportlab internals change
    pdfmetrics = None
    TTFont = None


_CACHED_FONT_FAMILY = None


def _find_existing_font(paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def _register_arabic_font() -> str:
    """Register a TrueType font that supports Arabic glyphs with ReportLab.

    Returns the font family name to be used in CSS. Falls back to "DejaVu Sans"
    if registration fails. This function caches its result across calls.
    """
    global _CACHED_FONT_FAMILY
    if _CACHED_FONT_FAMILY:
        return _CACHED_FONT_FAMILY

    fallback = "DejaVu Sans"
    if not (pdfmetrics and TTFont):
        _CACHED_FONT_FAMILY = fallback
        return _CACHED_FONT_FAMILY

    # Common Arabic-capable TTFs on major platforms
    candidates = []

    # Prefer a project-provided font under static/fonts/
    try:
        static_dirs = list(getattr(settings, "STATICFILES_DIRS", []))
    except Exception:
        static_dirs = []
    for base in static_dirs:
        for rel in (
            "fonts/Amiri-Regular.ttf",
            "fonts/Cairo-Regular.ttf",
            "fonts/NotoNaskhArabic-Regular.ttf",
            "fonts/Tajawal-Regular.ttf",
            "fonts/DejaVuSans.ttf",
        ):
            candidates.append(os.path.join(str(base), rel))

    if os.name == "nt":  # Windows
        candidates += [
            r"C:\\Windows\\Fonts\\Tahoma.ttf",
            r"C:\\Windows\\Fonts\\Arial.ttf",
            r"C:\\Windows\\Fonts\\Times.ttf",
            r"C:\\Windows\\Fonts\\DejaVuSans.ttf",
        ]
    else:
        # Linux
        candidates += [
            "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]
        # macOS
        candidates += [
            "/Library/Fonts/Arial Unicode.ttf",
            "/Library/Fonts/Arial.ttf",
        ]

    font_path = _find_existing_font(candidates)
    if not font_path:
        _CACHED_FONT_FAMILY = fallback
        return _CACHED_FONT_FAMILY

    try:
        # Register under a stable family name used by our CSS
        family = "AppArabic"
        if family not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(family, font_path))
        _CACHED_FONT_FAMILY = family
        return _CACHED_FONT_FAMILY
    except Exception:
        _CACHED_FONT_FAMILY = fallback
        return _CACHED_FONT_FAMILY


def _sanitize_filename(name: str) -> str:
    """Return a filesystem/HTTP-header safe filename (without path components).

    - Strips characters forbidden on Windows: \\ / : * ? " < > |
    - Trims leading/trailing dots/underscores/spaces
    - Ensures non-empty return
    """
    name = name or "report.pdf"
    # Remove path separators and other forbidden characters
    name = re.sub(r"[\\/:*?\"<>|]", "", name)
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip(" ._\t\n\r")
    return name or "report.pdf"


def render_to_pdf(template_src, context_dict=None, filename="report.pdf"):
    # Ensure language context is available in PDF templates
    lang = translation.get_language() or "en"
    ctx = dict(context_dict or {})
    ctx.setdefault("LANGUAGE_CODE", lang)
    ctx.setdefault("is_rtl", lang.startswith("ar"))
    # Provide a font family that supports Arabic if available
    try:
        ctx.setdefault("pdf_font_family", _register_arabic_font())
    except Exception:
        ctx.setdefault("pdf_font_family", "DejaVu Sans")

    # Note: Avoid overriding xhtml2pdf global defaults here to prevent
    # compatibility issues across versions. Arabic/RTL support is handled
    # via template CSS and the injected is_rtl flag.

    template = get_template(template_src)
    html = template.render(ctx)
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), dest=result, encoding="UTF-8")
    if not pdf.err:
        resp = HttpResponse(result.getvalue(), content_type="application/pdf")
        # Build a robust Content-Disposition supporting non-ASCII with RFC 5987
        safe = _sanitize_filename(filename)
        # Ensure extension
        if not safe.lower().endswith(".pdf"):
            safe += ".pdf"
        # ASCII fallback drops non-ASCII characters
        ascii_fallback = safe.encode("ascii", "ignore").decode() or "report.pdf"
        utf8_quoted = quote(safe)
        resp["Content-Disposition"] = (
            f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{utf8_quoted}'
        )
        return resp
    return HttpResponse("Error generating PDF", status=500)
