from django.db import models
from django.conf import settings
import uuid

class Certificate(models.Model):
    trainee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='certificates',
        limit_choices_to={'role': 'trainee'},
        verbose_name="المتدرب"
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='certificates',
        verbose_name="الدورة التدريبية"
    )
    certificate_number = models.CharField(max_length=50, unique=True, verbose_name="رقم الشهادة")
    verification_token = models.CharField(max_length=100, unique=True, verbose_name="رمز التحقق")
    pdf_file = models.FileField(upload_to='certificates/', blank=True, null=True, verbose_name="ملف الشهادة PDF")
    issued_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإصدار")

    def save(self, *args, **kwargs):
        if not self.verification_token:
            self.verification_token = str(uuid.uuid4())
        if not self.certificate_number:
            count = Certificate.objects.count() + 1
            self.certificate_number = f"CERT-1000-2026-{count:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"شهادة {self.trainee.get_full_name() or self.trainee.username} - {self.course.title}"

    class Meta:
        verbose_name = "شهادة التخرج"
        verbose_name_plural = "شهادات التخرج"
        unique_together = ('trainee', 'course')
