from django.db import models
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN        = 'super_admin',        'مسؤول النظام (Super Admin)'
        GOVERNORATE_ADMIN  = 'governorate_admin',  'مسؤول المحافظة'
        DIRECTOR           = 'director',           'مدير المبادرة'
        TRAINING_OFFICER   = 'training_officer',   'مسؤول التدريب'
        SUPERVISOR         = 'supervisor',          'المشرف'
        LECTURER           = 'lecturer',            'المحاضر'
        TRAINEE            = 'trainee',             'المتدرب'
        VISITOR            = 'visitor',             'الزائر'

    # ---- الدور الوظيفي ----
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.VISITOR,
        verbose_name="الدور الوظيفي"
    )

    # ---- ربط المستخدم بمحافظة ----
    # NULL مسموح للـ super_admin الذي يرى كل المحافظات
    governorate = models.ForeignKey(
        'locations.Governorate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name="المحافظة",
        help_text="اتركه فارغاً للمسؤول الوطني (Super Admin) فقط"
    )

    phone_number = models.CharField(max_length=15, blank=True, null=True, verbose_name="رقم الهاتف")
    national_id  = models.CharField(max_length=20, blank=True, null=True, verbose_name="الرقم الوطني")
    avatar       = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="الصورة الشخصية")
    gender       = models.CharField(
        max_length=10,
        choices=[('male', 'ذكر'), ('female', 'أنثى')],
        default='male',
        verbose_name="الجنس"
    )
    telegram_chat_id              = models.CharField(max_length=50, blank=True, null=True, verbose_name="معرف شات التليغرام")
    telegram_link_code            = models.CharField(max_length=50, blank=True, null=True, verbose_name="رمز ربط التليغرام")
    telegram_notifications_enabled = models.BooleanField(default=True, verbose_name="تفعيل إشعارات التليغرام")
    temp_password                 = models.CharField(max_length=128, blank=True, null=True, verbose_name="كلمة المرور المؤقتة/المولدة")

    # ---- خصائص الصلاحيات ----
    @property
    def is_super_admin(self):
        return self.role == self.Role.SUPER_ADMIN

    @property
    def is_governorate_admin(self):
        return self.role == self.Role.GOVERNORATE_ADMIN

    @property
    def is_national_level(self):
        """يملك صلاحيات وطنية (يرى جميع المحافظات)"""
        return self.role == self.Role.SUPER_ADMIN

    @property
    def can_manage_governorate(self):
        """يستطيع إدارة محافظته"""
        return self.role in (self.Role.SUPER_ADMIN, self.Role.GOVERNORATE_ADMIN, self.Role.DIRECTOR)

    def __str__(self):
        gov = f" — {self.governorate.name}" if self.governorate else " — وطني"
        return f"{self.get_full_name() or self.username} ({self.get_role_display()}){gov}"

    class Meta:
        verbose_name = "المستخدم"
        verbose_name_plural = "المستخدمون"


class TraineeProfile(models.Model):
    class Status(models.TextChoices):
        ACTIVE    = 'active',    'نشط'
        SUSPENDED = 'suspended', 'موقف'
        GRADUATED = 'graduated', 'خريج'

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='trainee_profile')

    # ---- الفرع الذي ينتمي إليه المتدرب ----
    branch = models.ForeignKey(
        'locations.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trainees',
        verbose_name="الفرع / مركز التدريب"
    )

    governorate = models.CharField(max_length=50, verbose_name="المحافظة (السكن)")
    district    = models.CharField(max_length=50, verbose_name="القضاء")
    university  = models.CharField(max_length=100, blank=True, null=True, verbose_name="المدرسة")
    college     = models.CharField(max_length=100, blank=True, null=True, verbose_name="الصف الدراسي")
    department  = models.CharField(max_length=100, blank=True, null=True, verbose_name="الفرع / الشعبة بالمدرسة")
    academic_stage = models.CharField(max_length=20, blank=True, null=True, verbose_name="المرحلة الدراسية (ابتدائي/متوسط/إعدادي)")
    specialty   = models.CharField(max_length=100, blank=True, null=True, verbose_name="المسار والاهتمام البرمجي")
    registration_date = models.DateField(auto_now_add=True, verbose_name="تاريخ التسجيل")
    status      = models.CharField(max_length=15, choices=Status.choices, default=Status.ACTIVE, verbose_name="حالة الحساب")
    points      = models.IntegerField(default=0, verbose_name="نقاط الطالب")

    group       = models.ForeignKey('courses.Group', on_delete=models.SET_NULL, null=True, blank=True, related_name='trainees', verbose_name="المجموعة")
    notes       = models.TextField(blank=True, null=True, verbose_name="ملاحظات")
    custom_training_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="الرقم التدريبي الخاص")

    def __str__(self):
        return f"ملف المتدرب: {self.user.get_full_name() or self.user.username}"

    @property
    def training_number(self):
        """رقم تدريبي فريد يشمل كود المحافظة: BAS-1000-0001"""
        if self.custom_training_number:
            return self.custom_training_number
        gov_code = self.user.governorate.code if self.user.governorate else "IRQ"
        return f"{gov_code}-1000-{self.id:04d}" if self.id else f"{gov_code}-1000-0000"

    # خصائص ديناميكية من المفاتيح الخارجية
    @property
    def attendance_percentage(self):
        from apps.attendance.models import Attendance
        total = Attendance.objects.filter(trainee=self.user).count()
        if total == 0:
            return 100.0
        present = Attendance.objects.filter(trainee=self.user, status='present').count()
        return round((present / total) * 100, 1)

    @property
    def absent_count(self):
        from apps.attendance.models import Attendance
        return Attendance.objects.filter(trainee=self.user, status='absent').count()

    @property
    def present_count(self):
        from apps.attendance.models import Attendance
        return Attendance.objects.filter(trainee=self.user, status='present').count()

    @property
    def completion_percentage(self):
        from apps.assignments.models import Project
        project = Project.objects.filter(trainee=self.user).first()
        return project.completion_percentage if project else 0

    class Meta:
        verbose_name = "ملف المتدرب"
        verbose_name_plural = "ملفات المتدربين"


class LecturerProfile(models.Model):
    user      = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='lecturer_profile')
    specialty = models.CharField(max_length=100, verbose_name="الاختصاص")
    bio       = models.TextField(blank=True, null=True, verbose_name="السيرة الذاتية")

    # ---- الفرع الذي يعمل فيه المحاضر ----
    branch = models.ForeignKey(
        'locations.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lecturers',
        verbose_name="الفرع / مركز التدريب"
    )

    def __str__(self):
        return f"ملف المحاضر: {self.user.get_full_name() or self.user.username}"

    class Meta:
        verbose_name = "ملف المحاضر"
        verbose_name_plural = "ملفات المحاضرين"


class SupervisorProfile(models.Model):
    user       = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='supervisor_profile')
    department = models.CharField(max_length=100, blank=True, null=True, verbose_name="القسم المسؤول عنه")

    def __str__(self):
        return f"ملف المشرف: {self.user.get_full_name() or self.user.username}"

    class Meta:
        verbose_name = "ملف المشرف"
        verbose_name_plural = "ملفات المشرفين"


class TraineeNote(models.Model):
    trainee    = models.ForeignKey(TraineeProfile, on_delete=models.CASCADE, related_name='staff_notes', verbose_name="المتدرب")
    author     = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_notes', verbose_name="مضيف الملاحظة")
    note       = models.TextField(verbose_name="نص الملاحظة والتوجيه")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإضافة")

    class Meta:
        verbose_name = "ملاحظة وتوجيه الكادر"
        verbose_name_plural = "ملاحظات وتوجيهات الكادر"
        ordering = ['-created_at']

    def __str__(self):
        author_name = self.author.get_full_name() if self.author else "غير محدد"
        return f"ملاحظة لـ {self.trainee} بواسطة {author_name}"
