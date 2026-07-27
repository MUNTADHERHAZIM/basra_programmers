from django.db import models
from django.conf import settings
from django.utils import timezone
import secrets

class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'present', 'حاضر'
        ABSENT = 'absent', 'غائب'
        LATE = 'late', 'متأخر'
        EXCUSED = 'excused', 'مجاز'

    class Method(models.TextChoices):
        QR = 'qr', 'QR Code'
        BARCODE = 'barcode', 'Barcode'
        MANUAL = 'manual', 'يدوي'

    trainee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'trainee'},
        related_name='attendances',
        verbose_name="المتدرب"
    )
    lecture = models.ForeignKey(
        'courses.Lecture',
        on_delete=models.CASCADE,
        related_name='attendances',
        verbose_name="المحاضرة"
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ABSENT,
        verbose_name="حالة الحضور"
    )
    check_in_time = models.DateTimeField(null=True, blank=True, verbose_name="وقت تسجيل الحضور")
    delay_minutes = models.PositiveIntegerField(default=0, verbose_name="دقائق التأخير")
    method = models.CharField(
        max_length=10,
        choices=Method.choices,
        default=Method.MANUAL,
        verbose_name="طريقة التحضير"
    )
    notes = models.TextField(blank=True, null=True, verbose_name="ملاحظات")

    def __str__(self):
        return f"{self.trainee.get_full_name() or self.trainee.username} - {self.lecture.title} - {self.get_status_display()}"

    class Meta:
        verbose_name = "سجل الحضور"
        verbose_name_plural = "سجلات الحضور"
        unique_together = ('trainee', 'lecture')


class LectureQRToken(models.Model):
    lecture = models.ForeignKey(
        'courses.Lecture',
        on_delete=models.CASCADE,
        related_name='qr_tokens',
        verbose_name="المحاضرة"
    )
    token = models.CharField(max_length=100, unique=True, verbose_name="الرمز المؤقت")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name="تاريخ الانتهاء")
    
    # Geofencing
    latitude = models.FloatField(null=True, blank=True, verbose_name="خط العرض")
    longitude = models.FloatField(null=True, blank=True, verbose_name="خط الطول")
    radius_meters = models.FloatField(default=50.0, verbose_name="نطاق التحقق (بالمتر)")

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(seconds=45)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"رمز QR لمحاضرة: {self.lecture.title} ({'منتهي' if self.is_expired else 'فعال'})"

    class Meta:
        verbose_name = "رمز حضور QR"
        verbose_name_plural = "رموز حضور QR"
