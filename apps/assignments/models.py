from django.db import models
from django.conf import settings

class Assignment(models.Model):
    group = models.ForeignKey(
        'courses.Group',
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name="المجموعة"
    )
    title = models.CharField(max_length=200, verbose_name="عنوان الواجب")
    description = models.TextField(verbose_name="وصف الواجب")
    file = models.FileField(upload_to='assignments/', blank=True, null=True, verbose_name="ملف مرفق")
    due_date = models.DateTimeField(verbose_name="تاريخ الاستحقاق والتسليم")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    def __str__(self):
        return f"{self.title} - {self.group.name}"

    class Meta:
        verbose_name = "الواجب الدراسي"
        verbose_name_plural = "الواجبات الدراسية"


class AssignmentSubmission(models.Model):
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='submissions',
        verbose_name="الواجب"
    )
    trainee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assignment_submissions',
        limit_choices_to={'role': 'trainee'},
        verbose_name="المتدرب"
    )
    file = models.FileField(upload_to='submissions/', verbose_name="ملف الحل المرفوع")
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name="وقت التسليم")
    grade = models.PositiveIntegerField(null=True, blank=True, verbose_name="الدرجة")
    feedback = models.TextField(blank=True, null=True, verbose_name="ملاحظات المصحح")
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='graded_submissions',
        limit_choices_to={'role': 'lecturer'},
        verbose_name="المصحح"
    )

    def __str__(self):
        return f"حل {self.trainee.get_full_name() or self.trainee.username} لـ {self.assignment.title}"

    class Meta:
        verbose_name = "تسليم الواجب"
        verbose_name_plural = "تسليمات الواجبات"
        unique_together = ('assignment', 'trainee')


class Project(models.Model):
    trainee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='projects',
        limit_choices_to={'role': 'trainee'},
        verbose_name="المتدرب"
    )
    title = models.CharField(max_length=200, verbose_name="عنوان المشروع")
    description = models.TextField(verbose_name="وصف المشروع")
    completion_percentage = models.PositiveIntegerField(default=0, verbose_name="نسبة الإنجاز")
    github_repo = models.URLField(blank=True, null=True, verbose_name="مستودع GitHub")
    demo_url = models.URLField(blank=True, null=True, verbose_name="رابط التجربة (Demo)")
    grade = models.PositiveIntegerField(null=True, blank=True, verbose_name="الدرجة النهائية")
    feedback = models.TextField(blank=True, null=True, verbose_name="ملاحظات وتوجيهات المدرب")
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='graded_projects',
        limit_choices_to={'role': 'lecturer'},
        verbose_name="المدرب المقيّم"
    )

    def __str__(self):
        return f"مشروع {self.trainee.get_full_name() or self.trainee.username}: {self.title}"

    class Meta:
        verbose_name = "المشروع البرمجي"
        verbose_name_plural = "المشاريع البرمجية"
