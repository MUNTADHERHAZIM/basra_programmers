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
