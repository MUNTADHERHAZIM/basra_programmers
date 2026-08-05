from django.db import models
from django.conf import settings

class Notification(models.Model):
    class Type(models.TextChoices):
        SYSTEM = 'system', 'داخل النظام'
        EMAIL = 'email', 'بريد إلكتروني'
        BOTH = 'both', 'كلاهما'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="المستخدم"
    )
    title = models.CharField(max_length=200, verbose_name="العنوان")
    message = models.TextField(verbose_name="نص الإشعار")
    notification_type = models.CharField(max_length=10, choices=Type.choices, default=Type.SYSTEM, verbose_name="نوع الإشعار")
    is_read = models.BooleanField(default=False, verbose_name="تم القراءة؟")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإرسال")

    def __str__(self):
        return f"{self.title} - {self.user.username}"

    class Meta:
        verbose_name = "الإشعار"
        verbose_name_plural = "الإشعارات"
        ordering = ['-created_at']


class InternalMessage(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        verbose_name="المرسل"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='received_messages',
        verbose_name="المستقبل (فردي)"
    )
    group = models.ForeignKey(
        'courses.Group',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='group_messages',
        verbose_name="المجموعة المستهدفة (جماعي)"
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='course_messages',
        verbose_name="المادة الدراسية المستهدفة"
    )
    content = models.TextField(verbose_name="نص الرسالة", blank=True, null=True)
    file = models.FileField(upload_to='messages/files/', blank=True, null=True, verbose_name="ملف مرفق")
    image = models.ImageField(upload_to='messages/images/', blank=True, null=True, verbose_name="صورة مرفقة")
    is_read = models.BooleanField(default=False, verbose_name="مقروءة؟")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإرسال")

    def __str__(self):
        target = self.group.name if self.group else (self.recipient.get_full_name() if self.recipient else "الجميع")
        return f"رسالة من {self.sender.get_full_name() or self.sender.username} إلى {target}"

    class Meta:
        verbose_name = "الرسالة الداخلية"
        verbose_name_plural = "الرسائل الداخلية"
        ordering = ['created_at']
