from django.db import models
from django.conf import settings
from django.utils import timezone


class Course(models.Model):
    """
    الدورة التدريبية — وطنية مشتركة بين جميع المحافظات.
    المنهج موحد، لكن كل محافظة تنشئ مجموعاتها الخاصة (Groups).
    """
    title       = models.CharField(max_length=200, verbose_name="عنوان الدورة")
    description = models.TextField(verbose_name="وصف الدورة")
    hours       = models.PositiveIntegerField(default=60, verbose_name="ساعات التدريب")
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "الدورة التدريبية"
        verbose_name_plural = "الدورات التدريبية"


class Group(models.Model):
    """
    المجموعة التدريبية — مرتبطة بمحافظة وفرع محددين.
    كود المجموعة فريد داخل المحافظة فقط (وليس على مستوى المنصة).
    """
    class Status(models.TextChoices):
        ACTIVE    = 'active',    'نشطة'
        COMPLETED = 'completed', 'مكتملة'
        PAUSED    = 'paused',    'متوقفة مؤقتاً'

    # ---- ربط المجموعة بالمحافظة والفرع ----
    governorate = models.ForeignKey(
        'locations.Governorate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='groups',
        verbose_name="المحافظة"
    )
    branch = models.ForeignKey(
        'locations.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='groups',
        verbose_name="الفرع / مركز التدريب"
    )

    name   = models.CharField(max_length=100, verbose_name="اسم المجموعة")
    code   = models.CharField(max_length=50, verbose_name="رمز المجموعة")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='groups', verbose_name="الدورة")
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to={'role': 'lecturer'},
        related_name='instructor_groups',
        verbose_name="المدرب/المحاضر"
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to={'role': 'supervisor'},
        related_name='supervisor_groups',
        verbose_name="المشرف"
    )
    classroom  = models.CharField(max_length=100, verbose_name="القاعة الدراسية")
    days       = models.CharField(max_length=200, verbose_name="أيام التدريب")
    start_time = models.TimeField(verbose_name="وقت البدء")
    end_time   = models.TimeField(verbose_name="وقت الانتهاء")
    status     = models.CharField(max_length=15, choices=Status.choices, default=Status.ACTIVE, verbose_name="حالة المجموعة")

    def __str__(self):
        return f"{self.name} ({self.code}) — {self.governorate.name}"

    @property
    def student_count(self):
        return self.trainees.count()

    class Meta:
        verbose_name = "المجموعة التدريبية"
        verbose_name_plural = "المجموعات التدريبية"
        # رمز المجموعة فريد داخل كل محافظة (لا تعارض بين المحافظات)
        unique_together = ('governorate', 'code')


class Lecture(models.Model):
    group      = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='lectures', verbose_name="المجموعة")
    title      = models.CharField(max_length=200, verbose_name="عنوان المحاضرة")
    content    = models.TextField(blank=True, null=True, verbose_name="محتوى المحاضرة")
    date       = models.DateField(verbose_name="التاريخ")
    start_time = models.TimeField(blank=True, null=True, verbose_name="وقت البدء")
    end_time   = models.TimeField(blank=True, null=True, verbose_name="وقت الانتهاء")
    video_url  = models.URLField(blank=True, null=True, verbose_name="رابط تسجيل المحاضرة")
    files      = models.FileField(upload_to='lectures/', blank=True, null=True, verbose_name="ملفات المحاضرة (PDF / مذكرات)")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='uploaded_lectures',
        verbose_name="تم الرفع بواسطة"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, verbose_name="تاريخ الإضافة")

    def __str__(self):
        return f"{self.title} - {self.group.name}"

    class Meta:
        verbose_name = "المحاضرة والمادة العلمية"
        verbose_name_plural = "المحاضرات والمواد العلمية"
        ordering = ['-date', '-created_at']


class DailyReport(models.Model):
    class Status(models.TextChoices):
        PENDING      = 'pending',      'قيد المراجعة'
        REVIEWED     = 'reviewed',     'تم الاطلاع عليها'
        ACTION_TAKEN = 'action_taken', 'تم اتخاذ إجراء'

    instructor  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='daily_reports',
        verbose_name="المدرب/المحاضر"
    )
    group       = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='daily_reports', verbose_name="الشعبة / المجموعة")
    lecture     = models.ForeignKey(Lecture, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports', verbose_name="المحاضرة المرتبطة")
    report_date = models.DateField(default=timezone.now, verbose_name="تاريخ التقرير")

    topics_covered       = models.TextField(verbose_name="المواضيع المشروحة والمهارات المغطاة")
    attendance_summary   = models.CharField(max_length=255, blank=True, null=True, verbose_name="ملخص الحضور والالتزام")
    outstanding_students = models.TextField(blank=True, null=True, verbose_name="الطلاب المتميزون خلال اليوم")
    struggling_students  = models.TextField(blank=True, null=True, verbose_name="الطلاب الذين يحتاجون متابعة أو دعم")
    challenges_and_notes = models.TextField(blank=True, null=True, verbose_name="التحديات والملاحظات العامة")

    status         = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name="حالة التقرير")
    admin_feedback = models.TextField(blank=True, null=True, verbose_name="رد الملاحظات الإدارية")
    reviewed_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_reports',
        verbose_name="المراجع الإداري"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإرسال")

    class Meta:
        verbose_name = "التقرير اليومي للمدرب"
        verbose_name_plural = "تقارير المدربين اليومية"
        ordering = ['-created_at']

    def __str__(self):
        return f"تقرير {self.instructor.get_full_name()} - {self.group.name} ({self.report_date})"
