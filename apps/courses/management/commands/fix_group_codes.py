from django.core.management.base import BaseCommand
from apps.courses.models import Group
from apps.portal.views import generate_clean_group_code


class Command(BaseCommand):
    help = "إصلاح وتحديث رموز المجموعات التدريبية القديمة أو المشوهة (مثل الذ-253 أو الـ-931) إلى رموز احترافية ونظيفة"

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='تحديث وتوحيد كافة رموز المجموعات وليس المشوهة فقط',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='معاينة التغييرات دون حفظها في قاعدة البيانات',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        update_all = options.get('all', False)
        
        groups = Group.objects.select_related('course', 'governorate').all()
        updated_count = 0
        
        self.stdout.write(self.style.NOTICE("🔍 فحص المجموعات التدريبية..."))
        
        for g in groups:
            code = (g.code or "").strip()
            # Detect distorted or messy codes like 'الذ-253' or 'الـ-931' or empty
            is_distorted = (
                not code or 
                code.startswith('الـ') or 
                code.startswith('الذ') or 
                code.startswith('الب') or 
                code.startswith('الأ') or
                code.startswith('ال') or
                len(code) < 3
            )
            
            if is_distorted or update_all:
                old_code = code
                new_code = generate_clean_group_code(g.course, g.governorate)
                
                if dry_run:
                    self.stdout.write(f" [معاينة] المجموعة '{g.name}' ({g.course.title if g.course else ''}): {old_code} -> {new_code}")
                else:
                    g.code = new_code
                    g.save()
                    self.stdout.write(self.style.SUCCESS(f" [تم التحديث] المجموعة '{g.name}' ({g.course.title if g.course else ''}): {old_code} -> {new_code}"))
                updated_count += 1
                
        if updated_count == 0:
            self.stdout.write(self.style.SUCCESS("✨ جميع رموز المجموعات التدريبية نظيفة وممتازة، لا توجد رموز مشوهة."))
        else:
            action_text = "تمت معاينة" if dry_run else "تم تحديث"
            self.stdout.write(self.style.SUCCESS(f"✅ اكتملت العملية! {action_text} {updated_count} مجموعة تدريبية بنجاح."))
