import os
import qrcode
from io import BytesIO
from django.conf import settings
from django.core.files.base import ContentFile
from .models import Certificate
try:
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except ImportError:
    canvas = None
    colors = None
    pdfmetrics = None
    TTFont = None
    landscape = None
    letter = None

try:
    import arabic_reshaper
except ImportError:
    arabic_reshaper = None

try:
    from bidi.algorithm import get_display
except ImportError:
    get_display = None

_FONTS_REGISTERED = False

def register_arabic_fonts():
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return 'Amiri-Bold', 'Amiri'
    
    regular_font_name = 'Helvetica'
    bold_font_name = 'Helvetica-Bold'
    
    # 1. Check project static/fonts directory
    base_dir = getattr(settings, 'BASE_DIR', os.getcwd())
    font_paths = [
        (os.path.join(base_dir, 'static', 'fonts', 'Amiri-Regular.ttf'), os.path.join(base_dir, 'static', 'fonts', 'Amiri-Bold.ttf')),
        (os.path.join(base_dir, 'staticfiles', 'fonts', 'Amiri-Regular.ttf'), os.path.join(base_dir, 'staticfiles', 'fonts', 'Amiri-Bold.ttf')),
        ('C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/arialbd.ttf'),
        ('C:/Windows/Fonts/tahoma.ttf', 'C:/Windows/Fonts/tahomabd.ttf'),
        ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
    ]
    
    for reg_path, bold_path in font_paths:
        if os.path.exists(reg_path) and os.path.exists(bold_path):
            try:
                pdfmetrics.registerFont(TTFont('ArabicRegular', reg_path))
                pdfmetrics.registerFont(TTFont('ArabicBold', bold_path))
                regular_font_name = 'ArabicRegular'
                bold_font_name = 'ArabicBold'
                _FONTS_REGISTERED = True
                break
            except Exception:
                continue

    return bold_font_name, regular_font_name


def ar_text(text):
    """Helper to reshape Arabic text and reverse direction for proper RTL rendering."""
    if not text:
        return ""
    try:
        if arabic_reshaper and get_display:
            # Reshape Arabic characters (connecting forms)
            reshaped = arabic_reshaper.reshape(str(text))
            # Convert to RTL display order
            return get_display(reshaped)
        return str(text)
    except Exception:
        return str(text)


class CertificateService:
    @staticmethod
    def generate_pdf(certificate_id, domain="http://localhost:8000"):
        try:
            cert = Certificate.objects.get(id=certificate_id)
        except Certificate.DoesNotExist:
            return None

        bold_font, regular_font = register_arabic_fonts()

        # Build public verification URL
        verify_url = f"{domain}/portal/verify/{cert.verification_token}/"

        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=1)
        qr.add_data(verify_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR code to memory buffer
        qr_buffer = BytesIO()
        qr_img.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)

        # Create PDF buffer in landscape mode
        pdf_buffer = BytesIO()
        p = canvas.Canvas(pdf_buffer, pagesize=landscape(letter))
        width, height = landscape(letter)

        # Draw a beautiful dark-blue & gold border
        p.setStrokeColor(colors.HexColor("#0f172a")) # Slate/Dark Blue
        p.setLineWidth(15)
        p.rect(15, 15, width - 30, height - 30)

        p.setStrokeColor(colors.HexColor("#d97706")) # Gold
        p.setLineWidth(4)
        p.rect(25, 25, width - 50, height - 50)

        # Header Titles
        p.setFillColor(colors.HexColor("#1e3a8a"))
        p.setFont(bold_font, 24)
        p.drawCentredString(width / 2, height - 80, ar_text("العتبة الحسينية المقدسة"))
        
        p.setFillColor(colors.HexColor("#10b981")) # Green Accent
        p.setFont(bold_font, 18)
        p.drawCentredString(width / 2, height - 110, ar_text("مبادرة 1000 مبرمج"))

        # Certificate Body
        p.setFillColor(colors.HexColor("#0f172a"))
        p.setFont(regular_font, 16)
        p.drawCentredString(width / 2, height - 170, ar_text("تشهد إدارة المبادرة بأن المتدرب:"))
        
        p.setFillColor(colors.HexColor("#d97706")) # Trainee Name in Gold
        p.setFont(bold_font, 26)
        trainee_name = cert.trainee.get_full_name() or cert.trainee.username
        p.drawCentredString(width / 2, height - 220, ar_text(trainee_name))

        p.setFillColor(colors.HexColor("#0f172a"))
        p.setFont(regular_font, 16)
        p.drawCentredString(width / 2, height - 260, ar_text("قد أكمل بنجاح الدورة التدريبية المتخصصة بعنوان:"))
        
        p.setFillColor(colors.HexColor("#1e3a8a")) # Course Title in Navy
        p.setFont(bold_font, 20)
        p.drawCentredString(width / 2, height - 300, ar_text(cert.course.title))

        p.setFillColor(colors.HexColor("#0f172a"))
        p.setFont(regular_font, 14)
        hours_text = f"والتي أقيمت بـ {cert.course.hours} ساعة تدريبية مكثفة."
        p.drawCentredString(width / 2, height - 340, ar_text(hours_text))

        # Draw QR code on bottom left
        from reportlab.lib.utils import ImageReader
        qr_reader = ImageReader(qr_buffer)
        p.drawImage(qr_reader, 50, 50, width=100, height=100)
        
        # QR Code Label
        p.setFillColor(colors.HexColor("#475569"))
        p.setFont(regular_font, 9)
        p.drawString(50, 36, ar_text("امسح للتحقق من الشهادة"))
        p.setFont(regular_font, 8)
        p.drawString(50, 24, f"No: {cert.certificate_number}")

        # Signature on bottom right
        p.setFillColor(colors.HexColor("#0f172a"))
        p.setFont(bold_font, 13)
        p.drawRightString(width - 50, 90, ar_text("توقيع إدارة المبادرة"))
        p.setFont(regular_font, 11)
        p.drawRightString(width - 50, 70, ar_text("العتبة الحسينية المقدسة"))
        
        # Draw signature line
        p.setStrokeColor(colors.HexColor("#94a3b8"))
        p.setLineWidth(1)
        p.line(width - 200, 110, width - 50, 110)

        # Finalize PDF
        p.showPage()
        p.save()

        # Save buffer to model
        pdf_buffer.seek(0)
        file_name = f"cert_{cert.certificate_number}.pdf"
        cert.pdf_file.save(file_name, ContentFile(pdf_buffer.read()), save=True)
        return cert.pdf_file.url
