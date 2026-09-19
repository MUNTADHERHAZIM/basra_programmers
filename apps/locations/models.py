from django.db import models


class Governorate(models.Model):
    """
    نموذج المحافظة — العنصر الأساسي للعزل متعدد المستأجرين.
    كل بيانات المنصة (مجموعات، متدربون، تقارير) مرتبطة بمحافظة محددة.
    """
    class Status(models.TextChoices):
        ACTIVE = 'active', 'نشطة'
        INACTIVE = 'inactive', 'غير نشطة'
        COMING_SOON = 'coming_soon', 'قريباً'

    name = models.CharField(max_length=100, unique=True, verbose_name="اسم المحافظة")
    code = models.CharField(
        max_length=5,
        unique=True,
        verbose_name="كود المحافظة",
        help_text="مثال: BAS للبصرة، BGH لبغداد، NJF للنجف"
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.COMING_SOON,
        verbose_name="حالة المحافظة"
    )
    launch_date = models.DateField(null=True, blank=True, verbose_name="تاريخ الإطلاق")
    logo = models.ImageField(
        upload_to='governorates/logos/',
        blank=True, null=True,
        verbose_name="شعار المحافظة"
    )
    cover_image = models.ImageField(
        upload_to='governorates/covers/',
        blank=True, null=True,
        verbose_name="صورة الغلاف"
    )
    description = models.TextField(blank=True, null=True, verbose_name="وصف النشاط في المحافظة")
    contact_email = models.EmailField(blank=True, null=True, verbose_name="البريد الإلكتروني للتواصل")
    contact_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="رقم التواصل")
    order = models.PositiveSmallIntegerField(default=0, verbose_name="ترتيب العرض")

    class Meta:
        verbose_name = "المحافظة"
        verbose_name_plural = "المحافظات"
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def active_trainees_count(self):
        """عدد المتدربين النشطين في هذه المحافظة"""
        from apps.users.models import TraineeProfile
        return TraineeProfile.objects.filter(
            user__governorate=self,
            status='active'
        ).count()

    @property
    def active_groups_count(self):
        """عدد المجموعات النشطة في هذه المحافظة"""
        from apps.courses.models import Group
        return Group.objects.filter(
            governorate=self,
            status='active'
        ).count()


class Branch(models.Model):
    """
    فرع أو مركز تدريب داخل المحافظة.
    مثال: مركز تدريب البصرة الجنوبي، مركز العشار
    """
    class Status(models.TextChoices):
        ACTIVE = 'active', 'نشط'
        INACTIVE = 'inactive', 'غير نشط'

    governorate = models.ForeignKey(
        Governorate,
        on_delete=models.CASCADE,
        related_name='branches',
        verbose_name="المحافظة"
    )
    name = models.CharField(max_length=150, verbose_name="اسم الفرع / المركز")
    code = models.CharField(max_length=10, verbose_name="كود الفرع")
    address = models.TextField(blank=True, null=True, verbose_name="العنوان التفصيلي")
    latitude = models.FloatField(null=True, blank=True, verbose_name="خط العرض")
    longitude = models.FloatField(null=True, blank=True, verbose_name="خط الطول")
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="الحالة"
    )
    contact_person = models.CharField(max_length=100, blank=True, null=True, verbose_name="المسؤول عن الفرع")
    contact_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="هاتف الفرع")

    class Meta:
        verbose_name = "الفرع / مركز التدريب"
        verbose_name_plural = "الفروع ومراكز التدريب"
        # كود الفرع يجب أن يكون فريداً داخل المحافظة فقط
        unique_together = ('governorate', 'code')
        ordering = ['governorate', 'name']

    def __str__(self):
        return f"{self.name} — {self.governorate.name}"
