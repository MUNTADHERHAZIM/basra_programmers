from django.db import models
from django.conf import settings

class Badge(models.Model):
    name = models.CharField(max_length=100, verbose_name="اسم الشارة")
    description = models.TextField(verbose_name="وصف الشارة")
    icon_name = models.CharField(max_length=50, default="award", verbose_name="أيقونة الشارة") # Bootstrap/FontAwesome icon
    points_required = models.PositiveIntegerField(default=100, verbose_name="النقاط المطلوبة لفتحها")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "شارة تفوق"
        verbose_name_plural = "شارات التفوق"


class TraineeBadge(models.Model):
    trainee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='earned_badges',
        limit_choices_to={'role': 'trainee'},
        verbose_name="المتدرب"
    )
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='holders', verbose_name="الشارة")
    unlocked_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الحصول عليها")

    def __str__(self):
        return f"{self.trainee.get_full_name() or self.trainee.username} حصل على شارة {self.badge.name}"

    class Meta:
        verbose_name = "شارة متدرب"
        verbose_name_plural = "شارات المتدربين"
        unique_together = ('trainee', 'badge')


class ActivityPointsLog(models.Model):
    trainee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='points_logs',
        limit_choices_to={'role': 'trainee'},
        verbose_name="المتدرب"
    )
    points = models.IntegerField(verbose_name="النقاط الممنوحة")
    reason = models.CharField(max_length=200, verbose_name="السبب")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="التاريخ والوقت")

    def __str__(self):
        return f"{self.trainee.get_full_name() or self.trainee.username} {self.points:+} نقطة لسبب: {self.reason}"

    class Meta:
        verbose_name = "سجل نقاط الفعالية"
        verbose_name_plural = "سجلات نقاط الفعاليات"
