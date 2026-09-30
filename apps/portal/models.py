from django.db import models
from django.core.validators import FileExtensionValidator


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

    @property
    def embed_video_url(self):
        if not self.video_url:
            return None
        import re
        url = self.video_url.strip()
        # YouTube matches (watch?v=, youtu.be/, shorts/, embed/)
        yt_match = re.search(r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/|youtube\.com\/shorts\/)([^"&?\/ ]{11})', url)
        if yt_match:
            return f"https://www.youtube.com/embed/{yt_match.group(1)}"
        # Vimeo
        vimeo_match = re.search(r'vimeo\.com\/(?:channels\/(?:\w+\/)?|groups\/([^\/]*)\/videos\/|album\/(\d+)\/video\/|video\/|)(\d+)', url)
        if vimeo_match:
            v_id = vimeo_match.group(3) or vimeo_match.group(2) or vimeo_match.group(1)
            if v_id:
                return f"https://player.vimeo.com/video/{v_id}"
        # Google Drive
        drive_match = re.search(r'drive\.google\.com\/file\/d\/([a-zA-Z0-9_-]+)', url)
        if drive_match:
            return f"https://drive.google.com/file/d/{drive_match.group(1)}/preview"
        return None

    def __str__(self):
        scope = self.governorate.name if self.governorate else "وطني"
        return f"{self.get_media_type_display()}: {self.title} [{scope}]"

    class Meta:
        verbose_name = "ميديا وإعلام المبادرة"
        verbose_name_plural = "مركز ميديا وإعلام المبادرة"
        ordering = ['-created_at']


class LearningInstruction(models.Model):
    """دروس وإرشادات قصيرة يمكن للإدارة نشرها للمدربين والمتدربين."""

    class Audience(models.TextChoices):
        ALL = 'all', 'المدربون والمتدربون'
        TRAINEES = 'trainees', 'المتدربون فقط'
        TRAINERS = 'trainers', 'المدربون فقط'

    title = models.CharField(max_length=200, verbose_name="عنوان الدرس")
    summary = models.CharField(max_length=300, verbose_name="ملخص قصير")
    content = models.TextField(blank=True, verbose_name="شرح الدرس")
    audience = models.CharField(max_length=20, choices=Audience.choices, default=Audience.ALL, verbose_name="يظهر إلى")
    icon = models.CharField(max_length=50, default="fa-lightbulb", verbose_name="أيقونة Font Awesome", help_text="مثال: fa-code أو fa-star")
    video_file = models.FileField(
        upload_to='learning/videos/', blank=True, null=True, verbose_name="فيديو تعليمي مرفوع",
        validators=[FileExtensionValidator(allowed_extensions=['mp4', 'webm', 'ogg', 'mov'])],
    )
    video_url = models.URLField(blank=True, verbose_name="رابط فيديو تعليمي", help_text="اختياري: رابط YouTube أو Vimeo أو Drive")
    is_published = models.BooleanField(default=True, verbose_name="منشور")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتيب الظهور")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإضافة")

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = "تعليمة / درس"
        verbose_name_plural = "دليل التعليمات والدروس"

    def __str__(self):
        return self.title


class ContactMessage(models.Model):
    """
    رسائل وتذاكر الدعم والاستفسارات والمشاكل والاشتراكات في المبادرة
    """
    class Category(models.TextChoices):
        GENERAL = 'general', 'استفسار عام عن المبادرة'
        REGISTRATION = 'registration', 'الاشتراك والتسجيل والقبول'
        TECHNICAL = 'technical', 'مشكلة تقنية أو خلل في المنصة'
        COURSES = 'courses', 'استفسار عن الدورات والمناهج'
        CERTIFICATES = 'certificates', 'الشهادات والنتائج'
        SUGGESTION = 'suggestion', 'اقتراح أو فكرة تطويرية'
        OTHER = 'other', 'أخرى'

    class Status(models.TextChoices):
        NEW = 'new', 'جديدة / قيد الانتظار'
        IN_PROGRESS = 'in_progress', 'قيد المراجعة والمتابعة'
        RESOLVED = 'resolved', 'تم الحل والرد'
        CLOSED = 'closed', 'مغلقة'

    class Priority(models.TextChoices):
        LOW = 'low', 'منخفضة'
        NORMAL = 'normal', 'عادية'
        URGENT = 'urgent', 'عاجلة'

    user = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contact_messages',
        verbose_name="المستخدم المسجل (إن وجد)"
    )
    name = models.CharField(max_length=150, verbose_name="الاسم الكامل")
    email = models.EmailField(verbose_name="البريد الإلكتروني")
    phone = models.CharField(max_length=30, blank=True, null=True, verbose_name="رقم الهاتف / واتساب")
    governorate = models.ForeignKey(
        'locations.Governorate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contact_messages',
        verbose_name="المحافظة"
    )

    category = models.CharField(max_length=30, choices=Category.choices, default=Category.GENERAL, verbose_name="نوع الاستفسار")
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL, verbose_name="الأولوية")
    subject = models.CharField(max_length=250, verbose_name="عنوان الرسالة / الموضوع")
    message = models.TextField(verbose_name="نص الرسالة / تفاصيل الاستفسار")
    attachment = models.FileField(upload_to='support_attachments/', blank=True, null=True, verbose_name="مرفق اختياري (صورة/مستند)")

    # Admin handling
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, verbose_name="حالة الرسالة")
    admin_notes = models.TextField(blank=True, null=True, verbose_name="ملاحظات الإدارة الداخلية")
    admin_reply = models.TextField(blank=True, null=True, verbose_name="رد الإدارة المرسل")
    handled_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_support_tickets',
        verbose_name="المسؤول المتابع"
    )
    is_read = models.BooleanField(default=False, verbose_name="تمت قراءتها من الإدارة")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإرسال")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")

    def __str__(self):
        return f"[{self.get_category_display()}] {self.subject} - {self.name}"

    class Meta:
        verbose_name = "رسالة تواصل واستفسار"
        verbose_name_plural = "رسائل التواصل والاستفسارات"
        ordering = ['-created_at']

