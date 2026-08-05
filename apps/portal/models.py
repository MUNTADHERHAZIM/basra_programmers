from django.db import models

class SiteConfiguration(models.Model):
    site_name = models.CharField(max_length=100, default="1000 مبرمج", verbose_name="اسم الموقع/المبادرة")
    sub_title = models.CharField(max_length=150, default="العتبة الحسينية المقدسة", verbose_name="العنوان الفرعي")
    logo = models.ImageField(upload_to='site/', blank=True, null=True, verbose_name="شعار المبادرة")

    def __str__(self):
        return "إعدادات الموقع الشاملة"

    class Meta:
        verbose_name = "إعدادات الموقع"
        verbose_name_plural = "إعدادات الموقع"


class InitiativeMedia(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = 'image', 'صورة'
        VIDEO = 'video', 'فيديو'
        ANNOUNCEMENT = 'announcement', 'إعلان / خبر'

    title = models.CharField(max_length=250, verbose_name="العنوان")
    description = models.TextField(blank=True, null=True, verbose_name="الوصف والتفاصيل")
    media_type = models.CharField(max_length=20, choices=MediaType.choices, default=MediaType.IMAGE, verbose_name="نوع المحتوى")
    image = models.ImageField(upload_to='initiative_media/images/', blank=True, null=True, verbose_name="الصورة المرفقة")
    video_file = models.FileField(upload_to='initiative_media/videos/', blank=True, null=True, verbose_name="ملف الفيديو")
    video_url = models.URLField(blank=True, null=True, verbose_name="رابط فيديو (YouTube / Drive / Vimeo)")
    attachment = models.FileField(upload_to='initiative_media/docs/', blank=True, null=True, verbose_name="ملف مرفق إضافي")
    is_public = models.BooleanField(default=True, verbose_name="ظاهر للجميع (العامة والطلاب)")
    created_by = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, verbose_name="الناشر")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ النشر")

    def __str__(self):
        return f"{self.get_media_type_display()}: {self.title}"

    class Meta:
        verbose_name = "ميديا وإعلام المبادرة"
        verbose_name_plural = "مركز ميديا وإعلام المبادرة"
        ordering = ['-created_at']

