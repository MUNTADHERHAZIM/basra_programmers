import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("portal", "0003_add_governorate_scope")]

    operations = [
        migrations.CreateModel(
            name="LearningInstruction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200, verbose_name="عنوان الدرس")),
                ("summary", models.CharField(max_length=300, verbose_name="ملخص قصير")),
                ("content", models.TextField(blank=True, verbose_name="شرح الدرس")),
                ("audience", models.CharField(choices=[("all", "المدربون والمتدربون"), ("trainees", "المتدربون فقط"), ("trainers", "المدربون فقط")], default="all", max_length=20, verbose_name="يظهر إلى")),
                ("icon", models.CharField(default="fa-lightbulb", help_text="مثال: fa-code أو fa-star", max_length=50, verbose_name="أيقونة Font Awesome")),
                ("video_file", models.FileField(blank=True, null=True, upload_to="learning/videos/", validators=[django.core.validators.FileExtensionValidator(allowed_extensions=["mp4", "webm", "ogg", "mov"])], verbose_name="فيديو تعليمي مرفوع")),
                ("video_url", models.URLField(blank=True, help_text="اختياري: رابط YouTube أو Vimeo أو Drive", verbose_name="رابط فيديو تعليمي")),
                ("is_published", models.BooleanField(default=True, verbose_name="منشور")),
                ("order", models.PositiveIntegerField(default=0, verbose_name="ترتيب الظهور")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإضافة")),
            ],
            options={"ordering": ["order", "-created_at"], "verbose_name": "تعليمة / درس", "verbose_name_plural": "دليل التعليمات والدروس"},
        ),
    ]
