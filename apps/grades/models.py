from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

class TraineeEvaluation(models.Model):
    trainee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trainee_evaluations',
        limit_choices_to={'role': 'trainee'},
        verbose_name="المتدرب"
    )
    lecture = models.ForeignKey(
        'courses.Lecture',
        on_delete=models.CASCADE,
        related_name='student_evaluations',
        verbose_name="المحاضرة"
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='evaluations_made',
        limit_choices_to={'role': 'lecturer'},
        verbose_name="المقيّم"
    )
    
    # 9 Evaluation Fields (1 to 10)
    commitment = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(10)], verbose_name="الالتزام")
    attendance = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(10)], verbose_name="الحضور")
    assignments = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(10)], verbose_name="الواجبات")
    participation = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(10)], verbose_name="المشاركة")
    coding = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(10)], verbose_name="البرمجة")
    projects = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(10)], verbose_name="المشاريع")
    teamwork = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(10)], verbose_name="العمل الجماعي")
    behavior = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(10)], verbose_name="السلوك")
    communication = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(10)], verbose_name="التواصل")
    
    average_grade = models.DecimalField(max_digits=4, decimal_places=2, default=0.0, verbose_name="المتوسط")
    grade_letter = models.CharField(max_length=20, default="", verbose_name="التقدير")
    notes = models.TextField(blank=True, null=True, verbose_name="ملاحظات")

    def save(self, *args, **kwargs):
        fields = [
            self.commitment, self.attendance, self.assignments, self.participation,
            self.coding, self.projects, self.teamwork, self.behavior, self.communication
        ]
        self.average_grade = sum(fields) / len(fields)
        
        # Calculate grade letter in Arabic
        if self.average_grade >= 9.0:
            self.grade_letter = "ممتاز"
        elif self.average_grade >= 8.0:
            self.grade_letter = "جيد جداً"
        elif self.average_grade >= 7.0:
            self.grade_letter = "جيد"
        elif self.average_grade >= 6.0:
            self.grade_letter = "مقبول"
        else:
            self.grade_letter = "ضعيف"
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"تقييم {self.trainee.get_full_name() or self.trainee.username} - محاضرة {self.lecture.title}"

    class Meta:
        verbose_name = "تقييم المتدرب"
        verbose_name_plural = "تقييمات المتدربين"
        unique_together = ('trainee', 'lecture')


class LecturerEvaluation(models.Model):
    lecturer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_ratings',
        limit_choices_to={'role': 'lecturer'},
        verbose_name="المحاضر"
    )
    lecture = models.ForeignKey(
        'courses.Lecture',
        on_delete=models.CASCADE,
        related_name='lecturer_evals',
        verbose_name="المحاضرة"
    )
    trainee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submitted_ratings',
        limit_choices_to={'role': 'trainee'},
        verbose_name="المتدرب المقيّم"
    )
    
    # 5 Ratings (1 to 5)
    explanation_clarity = models.PositiveIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="وضوح الشرح")
    commitment = models.PositiveIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="الالتزام")
    material_quality = models.PositiveIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="جودة المادة")
    interaction = models.PositiveIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="التفاعل")
    time_management = models.PositiveIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="إدارة الوقت")
    
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0, verbose_name="متوسط التقييم")
    notes = models.TextField(blank=True, null=True, verbose_name="ملاحظات إضافية")

    def save(self, *args, **kwargs):
        fields = [
            self.explanation_clarity, self.commitment, self.material_quality,
            self.interaction, self.time_management
        ]
        self.average_rating = sum(fields) / len(fields)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"تقييم المحاضر {self.lecturer.get_full_name() or self.lecturer.username} من {self.trainee.get_full_name() or self.trainee.username}"

    class Meta:
        verbose_name = "تقييم المحاضر"
        verbose_name_plural = "تقييمات المحاضرين"
        unique_together = ('lecture', 'trainee')
