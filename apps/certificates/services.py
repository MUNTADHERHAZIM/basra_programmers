import os
import qrcode
from io import BytesIO
from django.conf import settings
from django.core.files.base import ContentFile
from .models import Certificate
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

class CertificateService:
    @staticmethod
    def generate_pdf(certificate_id, domain="http://localhost:8000"):
        try:
            cert = Certificate.objects.get(id=certificate_id)
        except Certificate.DoesNotExist:
            return None

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
        p.setFont("Helvetica-Bold", 24)
        p.drawCentredString(width / 2, height - 80, "العتبة الحسينية المقدسة")
        
        p.setFillColor(colors.HexColor("#10b981")) # Green Accent
        p.setFont("Helvetica-Bold", 18)
        p.drawCentredString(width / 2, height - 110, "مبادرة 1000 مبرمج في البصرة")

        # Certificate Body
        p.setFillColor(colors.HexColor("#0f172a"))
        p.setFont("Helvetica", 16)
        p.drawCentredString(width / 2, height - 170, "تشهد إدارة المبادرة بأن المتدرب:")
        
        p.setFillColor(colors.HexColor("#d97706")) # Trainee Name in Gold
        p.setFont("Helvetica-Bold", 26)
        trainee_name = cert.trainee.get_full_name() or cert.trainee.username
        p.drawCentredString(width / 2, height - 220, trainee_name)

        p.setFillColor(colors.HexColor("#0f172a"))
        p.setFont("Helvetica", 16)
        p.drawCentredString(width / 2, height - 260, "قد أكمل بنجاح الدورة التدريبية المتخصصة بعنوان:")
        
        p.setFillColor(colors.HexColor("#1e3a8a")) # Course Title in Navy
        p.setFont("Helvetica-Bold", 20)
        p.drawCentredString(width / 2, height - 300, cert.course.title)

        p.setFillColor(colors.HexColor("#0f172a"))
        p.setFont("Helvetica", 14)
        p.drawCentredString(width / 2, height - 340, f"والتي أقيمت بـ {cert.course.hours} ساعة تدريبية مكثفة.")

        # Draw QR code on bottom left
        from reportlab.lib.utils import ImageReader
        qr_reader = ImageReader(qr_buffer)
        p.drawImage(qr_reader, 50, 50, width=100, height=100)
        
        # QR Code Label
        p.setFillColor(colors.HexColor("#475569"))
        p.setFont("Helvetica", 8)
        p.drawString(50, 35, "امسح للتحقق من الشهادة")
        p.drawString(50, 25, f"رقم: {cert.certificate_number}")

        # Signature on bottom right
        p.setFillColor(colors.HexColor("#0f172a"))
        p.setFont("Helvetica-Bold", 12)
        p.drawRightString(width - 50, 90, "توقيع إدارة المبادرة")
        p.setFont("Helvetica", 10)
        p.drawRightString(width - 50, 70, "العتبة الحسينية المقدسة")
        
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
