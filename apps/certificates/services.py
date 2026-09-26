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
_REGULAR_FONT = 'Helvetica'
_BOLD_FONT = 'Helvetica-Bold'

def register_arabic_fonts():
    global _FONTS_REGISTERED, _REGULAR_FONT, _BOLD_FONT
    if _FONTS_REGISTERED:
        return _BOLD_FONT, _REGULAR_FONT
    
    # 1. Check project static/fonts directory
    base_dir = str(getattr(settings, 'BASE_DIR', os.getcwd()))
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
                _REGULAR_FONT = 'ArabicRegular'
                _BOLD_FONT = 'ArabicBold'
                _FONTS_REGISTERED = True
                break
            except Exception:
                continue

    return _BOLD_FONT, _REGULAR_FONT


# Complete pure-Python Arabic reshaping & BiDi engine (works without external C/packages)
ARABIC_FORMS_TABLE = {
    0x0621: (0xFE80, 0xFE80, 0xFE80, 0xFE80), # ء
    0x0622: (0xFE81, 0xFE82, 0xFE81, 0xFE82), # آ
    0x0623: (0xFE83, 0xFE84, 0xFE83, 0xFE84), # أ
    0x0624: (0xFE85, 0xFE86, 0xFE85, 0xFE86), # ؤ
    0x0625: (0xFE87, 0xFE88, 0xFE87, 0xFE88), # إ
    0x0626: (0xFE89, 0xFE8A, 0xFE8B, 0xFE8C), # ئ
    0x0627: (0xFE8D, 0xFE8E, 0xFE8D, 0xFE8E), # ا
    0x0628: (0xFE8F, 0xFE90, 0xFE91, 0xFE92), # ب
    0x0629: (0xFE93, 0xFE94, 0xFE93, 0xFE94), # ة
    0x062A: (0xFE95, 0xFE96, 0xFE97, 0xFE98), # ت
    0x062B: (0xFE99, 0xFE9A, 0xFE9B, 0xFE9C), # ث
    0x062C: (0xFE9D, 0xFE9E, 0xFE9F, 0xFEA0), # ج
    0x062D: (0xFEA1, 0xFEA2, 0xFEA3, 0xFEA4), # ح
    0x062E: (0xFEA5, 0xFEA6, 0xFEA7, 0xFEA8), # خ
    0x062F: (0xFEA9, 0xFEAA, 0xFEA9, 0xFEAA), # د
    0x0630: (0xFEAB, 0xFEAC, 0xFEAB, 0xFEAC), # ذ
    0x0631: (0xFEAD, 0xFEAE, 0xFEAD, 0xFEAE), # ر
    0x0632: (0xFEAF, 0xFEB0, 0xFEAF, 0xFEB0), # ز
    0x0633: (0xFEB1, 0xFEB2, 0xFEB3, 0xFEB4), # س
    0x0634: (0xFEB5, 0xFEB6, 0xFEB7, 0xFEB8), # ش
    0x0635: (0xFEB9, 0xFEBA, 0xFEBB, 0xFEBC), # ص
    0x0636: (0xFEBD, 0xFEBE, 0xFEBF, 0xFEC0), # ض
    0x0637: (0xFEC1, 0xFEC2, 0xFEC3, 0xFEC4), # ط
    0x0638: (0xFEC5, 0xFEC6, 0xFEC7, 0xFEC8), # ظ
    0x0639: (0xFEC9, 0xFECA, 0xFECB, 0xFECC), # ع
    0x063A: (0xFECD, 0xFECE, 0xFECF, 0xFED0), # غ
    0x0641: (0xFED1, 0xFED2, 0xFED3, 0xFED4), # ف
    0x0642: (0xFED5, 0xFED6, 0xFED7, 0xFED8), # ق
    0x0643: (0xFED9, 0xFEDA, 0xFEDB, 0xFEDC), # ك
    0x0644: (0xFEDD, 0xFEDE, 0xFEDF, 0xFEE0), # ل
    0x0645: (0xFEE1, 0xFEE2, 0xFEE3, 0xFEE4), # م
    0x0646: (0xFEE5, 0xFEE6, 0xFEE7, 0xFEE8), # ن
    0x0647: (0xFEE9, 0xFEEA, 0xFEEB, 0xFEEC), # ه
    0x0648: (0xFEED, 0xFEEE, 0xFEED, 0xFEEE), # و
    0x0649: (0xFEEF, 0xFEF0, 0xFBE8, 0xFBE9), # ى
    0x064A: (0xFEF1, 0xFEF2, 0xFEF3, 0xFEF4), # ي
}

NON_CONNECTING_NEXT = {
    0x0621, 0x0622, 0x0623, 0x0624, 0x0625, 0x0627, 
    0x0629, 0x062F, 0x0630, 0x0631, 0x0632, 0x0648, 0x0649
}

def pure_python_reshape_arabic(text):
    if not text:
        return ""
    import re
    # Handle lam-alef ligatures first
    text = str(text)
    text = text.replace('\u0644\u0622', '\uFEF5')
    text = text.replace('\u0644\u0623', '\uFEF7')
    text = text.replace('\u0644\u0625', '\uFEF9')
    text = text.replace('\u0644\u0627', '\uFEFB')
    
    chars = list(text)
    n = len(chars)
    result = []
    
    for i, ch in enumerate(chars):
        code = ord(ch)
        if code not in ARABIC_FORMS_TABLE:
            result.append(ch)
            continue
            
        forms = ARABIC_FORMS_TABLE[code]
        prev_connects = False
        if i > 0:
            prev_code = ord(chars[i-1])
            if prev_code in ARABIC_FORMS_TABLE and prev_code not in NON_CONNECTING_NEXT:
                prev_connects = True
                
        next_connects = False
        if i < n - 1:
            next_code = ord(chars[i+1])
            if next_code in ARABIC_FORMS_TABLE and code not in NON_CONNECTING_NEXT:
                next_connects = True
                
        if prev_connects and next_connects:
            form = forms[3] # Medial
        elif prev_connects:
            form = forms[1] # Final
        elif next_connects:
            form = forms[2] # Initial
        else:
            form = forms[0] # Isolated
            
        result.append(chr(form))
    return ''.join(result)

def pure_python_bidi(text):
    if not text:
        return ""
    import re
    # Splits text into runs of Arabic vs LTR (numbers, punctuation, English)
    tokens = re.findall(r'[0-9]+|[a-zA-Z]+|[^0-9a-zA-Z\s]+|\s+', text)
    tokens.reverse()
    reversed_tokens = []
    for tok in tokens:
        if re.search(r'[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]', tok):
            reversed_tokens.append(tok[::-1])
        else:
            reversed_tokens.append(tok)
    return ''.join(reversed_tokens)


def ar_text(text):
    """Helper to reshape Arabic text and reverse direction for proper RTL rendering."""
    if not text:
        return ""
    raw_str = str(text)
    try:
        if arabic_reshaper and get_display:
            try:
                # Use standard configuration with ligature support
                reshaper = arabic_reshaper.ArabicReshaper(configuration={
                    'delete_harakat': False,
                    'support_ligatures': True,
                })
                reshaped = reshaper.reshape(raw_str)
            except Exception:
                reshaped = arabic_reshaper.reshape(raw_str)
            return get_display(reshaped)
    except Exception:
        pass
    
    # Fallback to 100% robust pure-Python implementation
    try:
        reshaped = pure_python_reshape_arabic(raw_str)
        return pure_python_bidi(reshaped)
    except Exception:
        return raw_str


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
