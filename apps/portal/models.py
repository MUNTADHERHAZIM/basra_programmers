from django.db import models


class SiteConfiguration(models.Model):
    """
    إعدادات الموقع — يمكن أن تكون وطنية (governorate=NULL) أو خاصة بمحافظة.
    يُعطى الأولوية للإعداد الخاص بالمحافظة عند وجوده.
    """
    governorate = models.OneToOneField(
        'locations.Governorate',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='site_config',
        verbose_name="المحافظة (اتركه فارغاً للإعداد الوطني الافتراضي)"
    )
    site_name = models.CharField(max_length=100, default="1000 مبرمج", verbose_name="اسم الموقع/المبادرة")
    sub_title = models.CharField(max_length=150, default="العتبة الحسينية المقدسة", verbose_name="العنوان الفرعي")
    logo      = models.ImageField(upload_to='site/', blank=True, null=True, verbose_name="شعار المبادرة")

    def __str__(self):
        if self.governorate:
            return f"إعدادات {self.governorate.name}"
        return "الإعدادات الوطنية الافتراضية"

    class Meta:
        verbose_name = "إعدادات الموقع"
        verbose_name_plural = "إعدادات الموقع"


class InitiativeMedia(models.Model):
    """
    ميديا وإعلام المبادرة.
    governorate=NULL → إعلان وطني يظهر لجميع المحافظات.
    governorate=محافظة محددة → يظهر لتلك المحافظة فقط.
    """
    class MediaType(models.TextChoices):
        IMAGE        = 'image',        'صورة'
        VIDEO        = 'video',        'فيديو'
        ANNOUNCEMENT = 'announcement', 'إعلان / خبر'

    # NULL = وطني (يظهر للجميع)، قيمة = محلي (يظهر للمحافظة فقط)
    governorate = models.ForeignKey(
        'locations.Governorate',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='media',
        verbose_name="المحافظة",
        help_text="اتركه فارغاً لجعل هذا المحتوى وطنياً يظهر لجميع المحافظات"
    )

    title       = models.CharField(max_length=250, verbose_name="العنوان")
    description = models.TextField(blank=True, null=True, verbose_name="الوصف والتفاصيل")
    media_type  = models.CharField(max_length=20, choices=MediaType.choices, default=MediaType.IMAGE, verbose_name="نوع المحتوى")
    image       = models.ImageField(upload_to='initiative_media/images/', blank=True, null=True, verbose_name="الصورة المرفقة")
    video_file  = models.FileField(upload_to='initiative_media/videos/', blank=True, null=True, verbose_name="ملف الفيديو")
    video_url   = models.URLField(blank=True, null=True, verbose_name="رابط فيديو (YouTube / Drive / Vimeo)")
    attachment  = models.FileField(upload_to='initiative_media/docs/', blank=True, null=True, verbose_name="ملف مرفق إضافي")
    is_public   = models.BooleanField(default=True, verbose_name="ظاهر للجميع (العامة والطلاب)")
    created_by  = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, verbose_name="الناشر")
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ النشر")

    def __str__(self):
        scope = self.governorate.name if self.governorate else "وطني"
        return f"{self.get_media_type_display()}: {self.title} [{scope}]"

    class Meta:
        verbose_name = "ميديا وإعلام المبادرة"
        verbose_name_plural = "مركز ميديا وإعلام المبادرة"
        ordering = ['-created_at']
