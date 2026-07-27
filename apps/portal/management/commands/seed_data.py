from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.users.models import CustomUser, TraineeProfile, LecturerProfile, SupervisorProfile
from apps.courses.models import Course, Group, Lecture
from apps.gamification.models import Badge, ActivityPointsLog, TraineeBadge
from apps.attendance.models import Attendance
from apps.grades.models import TraineeEvaluation
from apps.assignments.models import Assignment, Project
import datetime

class Command(BaseCommand):
    help = "Seeds the database with high-quality demo data for the 1000 Programmers platform."

    def handle(self, *args, **options):
        self.stdout.write("Starting database seeding...")

        # 1. Create Badges
        badges_data = [
            {"name": "حضور كامل", "description": "حضور 5 محاضرات متتالية دون غياب أو تأخير.", "icon_name": "award", "points_required": 50},
            {"name": "حلول مثالية", "description": "الحصول على درجة كاملة (10/10) في ثلاثة واجبات.", "icon_name": "star", "points_required": 100},
            {"name": "البرمجة النظيفة", "description": "كتابة كود برمجي منظم ومطابق للمعايير القياسية في المشاريع.", "icon_name": "code", "points_required": 150},
            {"name": "الروح القيادية", "description": "مساعدة الزملاء والتفاعل البناء في مشاريع الفريق العمل الجماعي.", "icon_name": "users", "points_required": 200},
        ]
        
        badges = []
        for badge_info in badges_data:
            badge, created = Badge.objects.get_or_create(
                name=badge_info["name"],
                defaults={
                    "description": badge_info["description"],
                    "icon_name": badge_info["icon_name"],
                    "points_required": badge_info["points_required"]
                }
            )
            badges.append(badge)
            if created:
                self.stdout.write(f"Badge '{badge.name}' created.")

        # 2. Create Users
        # Admin
        admin_user, created = CustomUser.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@1000programmers.org",
                "first_name": "أحمد",
                "last_name": "الحسني",
                "role": CustomUser.Role.SUPER_ADMIN,
                "is_staff": True,
                "is_superuser": True
            }
        )
        if created:
            admin_user.set_password("Password123")
            admin_user.save()
            self.stdout.write("Admin user created (admin / Password123).")

        # Director
        director_user, created = CustomUser.objects.get_or_create(
            username="director",
            defaults={
                "email": "director@1000programmers.org",
                "first_name": "حيدر",
                "last_name": "الموسوي",
                "role": CustomUser.Role.DIRECTOR,
                "is_staff": True
            }
        )
        if created:
            director_user.set_password("Password123")
            director_user.save()
            self.stdout.write("Director user created (director / Password123).")

        # Supervisor
        supervisor_user, created = CustomUser.objects.get_or_create(
            username="supervisor",
            defaults={
                "email": "supervisor@1000programmers.org",
                "first_name": "محمد",
                "last_name": "البصراوي",
                "role": CustomUser.Role.SUPERVISOR,
                "is_staff": True
            }
        )
        if created:
            supervisor_user.set_password("Password123")
            supervisor_user.save()
            SupervisorProfile.objects.get_or_create(user=supervisor_user, defaults={"department": "قسم المتابعة والإرشاد"})
            self.stdout.write("Supervisor user created (supervisor / Password123).")

        # Lecturer
        lecturer_user, created = CustomUser.objects.get_or_create(
            username="lecturer",
            defaults={
                "email": "lecturer@1000programmers.org",
                "first_name": "علي",
                "last_name": "الخفاجي",
                "role": CustomUser.Role.LECTURER,
                "is_staff": True
            }
        )
        if created:
            lecturer_user.set_password("Password123")
            lecturer_user.save()
            LecturerProfile.objects.get_or_create(
                user=lecturer_user,
                defaults={"specialty": "تطوير الويب المتكامل (Django/React)", "bio": "مهندس برمجيات وخبير بالبايثون ودجانغو خبرة 8 سنوات."}
            )
            self.stdout.write("Lecturer user created (lecturer / Password123).")

        # Trainees
        trainees_info = [
            {"username": "student1", "first_name": "مرتضى", "last_name": "حازم", "email": "muntadher@1000programmers.org", "gov": "البصرة", "dist": "العباسية", "uni": "جامعة البصرة", "col": "كلية الهندسة", "dept": "هندسة الحاسبات", "stage": "المرحلة الثالثة", "spec": "برمجة النظم"},
            {"username": "student2", "first_name": "مصطفى", "last_name": "سعد", "email": "mustafa@1000programmers.org", "gov": "البصرة", "dist": "الجبيلة", "uni": "جامعة البصرة", "col": "كلية العلوم", "dept": "علوم الحاسوب", "stage": "المرحلة الرابعة", "spec": "تطوير مواقع"},
            {"username": "student3", "first_name": "فاطمة", "last_name": "حسين", "email": "fatima@1000programmers.org", "gov": "البصرة", "dist": "العشار", "uni": "الجامعة التقنية الجنوبية", "col": "الكلية التقنية الهندسية", "dept": "هندسة تقنيات الحاسوب", "stage": "المرحلة الثانية", "spec": "تطبيقات الويب"},
            {"username": "student4", "first_name": "حسن", "last_name": "جواد", "email": "hassan@1000programmers.org", "gov": "البصرة", "dist": "القبلة", "uni": "جامعة البصرة", "col": "كلية تكنولوجيا المعلومات", "dept": "علم الحاسوب", "stage": "خريج", "spec": "تحليل بيانات"},
        ]

        trainees = []
        for info in trainees_info:
            user, created = CustomUser.objects.get_or_create(
                username=info["username"],
                defaults={
                    "email": info["email"],
                    "first_name": info["first_name"],
                    "last_name": info["last_name"],
                    "role": CustomUser.Role.TRAINEE
                }
            )
            if created:
                user.set_password("Password123")
                user.save()
            
            profile, created_profile = TraineeProfile.objects.get_or_create(
                user=user,
                defaults={
                    "governorate": info["gov"],
                    "district": info["dist"],
                    "university": info["uni"],
                    "college": info["col"],
                    "department": info["dept"],
                    "academic_stage": info["stage"],
                    "specialty": info["spec"],
                    "points": 120 if info["username"] == "student1" else 80
                }
            )
            trainees.append(user)
            self.stdout.write(f"Trainee user created ({user.username} / Password123).")

        # 3. Create Course
        course, created = Course.objects.get_or_create(
            title="تطوير الويب المتكامل بايثون ودجانغو (Web Development with Python & Django)",
            defaults={
                "description": "دورة احترافية متكاملة لتعليم أساسيات البايثون وبناء المنصات باستخدام إطار العمل دجانغو وقواعد بيانات PostgreSQL.",
                "hours": 120
            }
        )
        if created:
            self.stdout.write(f"Course '{course.title}' created.")

        # 4. Create Group
        group, created = Group.objects.get_or_create(
            code="BS-DJ-01",
            defaults={
                "name": "شعبة البصرة - المجموعة الأولى (بايثون)",
                "course": course,
                "instructor": lecturer_user,
                "supervisor": supervisor_user,
                "classroom": "القاعة الكبرى - الطابق الأول",
                "days": "الأحد، الثلاثاء، الخميس",
                "start_time": datetime.time(15, 0),
                "end_time": datetime.time(18, 0),
                "status": Group.Status.ACTIVE
            }
        )
        if created:
            self.stdout.write(f"Group '{group.name}' created.")

        # Associate trainees to the group
        for t in trainees:
            profile = t.trainee_profile
            if profile.group != group:
                profile.group = group
                profile.save()
        self.stdout.write("Associated trainees with the group.")

        # 5. Create Lectures
        lecture1, created = Lecture.objects.get_or_create(
            group=group,
            title="المحاضرة 1: مقدمة إلى بايثون وهيكلة الويب",
            defaults={
                "content": "مقدمة شاملة عن لغة بايثون، التثبيت، بيئة العمل الافتراضية، والمتغيرات وأنواع البيانات الأساسية.",
                "date": timezone.now().date() - datetime.timedelta(days=7),
                "start_time": datetime.time(15, 0),
                "end_time": datetime.time(18, 0),
            }
        )
        
        lecture2, created = Lecture.objects.get_or_create(
            group=group,
            title="المحاضرة 2: الكائنات والوظائف وبنى التحكم (OOP in Python)",
            defaults={
                "content": "شرح مفصل للبرمجة كائنية التوجه، الكلاسات، الوظائف، والشروط والحلقات التكرارية.",
                "date": timezone.now().date() - datetime.timedelta(days=4),
                "start_time": datetime.time(15, 0),
                "end_time": datetime.time(18, 0),
            }
        )

        lecture3, created = Lecture.objects.get_or_create(
            group=group,
            title="المحاضرة 3: مقدمة إلى إطار العمل دجانغو (Django Core)",
            defaults={
                "content": "التعرف على معمارية MVT، إنشاء المشروع الأول، إعداد التطبيقات وربط عناوين URLs.",
                "date": timezone.now().date() + datetime.timedelta(days=2),
                "start_time": datetime.time(15, 0),
                "end_time": datetime.time(18, 0),
            }
        )
        self.stdout.write("Lectures created.")

        # 6. Create Attendance logs
        for t in trainees:
            # Let student1 be Present, student2 Present, student3 Late, student4 Absent in Lecture 1
            status = Attendance.Status.PRESENT
            delay = 0
            if t.username == "student3":
                status = Attendance.Status.LATE
                delay = 15
            elif t.username == "student4":
                status = Attendance.Status.ABSENT
                
            Attendance.objects.get_or_create(
                trainee=t,
                lecture=lecture1,
                defaults={
                    "status": status,
                    "check_in_time": timezone.now() - datetime.timedelta(days=7),
                    "delay_minutes": delay,
                    "method": Attendance.Method.QR
                }
            )
            
            # Lecture 2
            Attendance.objects.get_or_create(
                trainee=t,
                lecture=lecture2,
                defaults={
                    "status": Attendance.Status.PRESENT,
                    "check_in_time": timezone.now() - datetime.timedelta(days=4),
                    "method": Attendance.Method.MANUAL
                }
            )
        self.stdout.write("Attendance records created.")

        # 7. Create Assignments
        assign1, created = Assignment.objects.get_or_create(
            group=group,
            title="الواجب الأول: خوارزمية البحث والترتيب في بايثون",
            defaults={
                "description": "كتابة برنامج بايثون يقوم بترتيب مصفوفة من العناصر أبجدياً وتصفيتها.",
                "due_date": timezone.now() - datetime.timedelta(days=2)
            }
        )

        assign2, created = Assignment.objects.get_or_create(
            group=group,
            title="الواجب الثاني: بناء تطبيق إدارة مهام بسيط بالـ Models",
            defaults={
                "description": "قم بإنشاء نموذج (Model) للمهام يحتوي على الحقول اللازمة وتثبيت قاعدة البيانات.",
                "due_date": timezone.now() + datetime.timedelta(days=5)
            }
        )
        self.stdout.write("Assignments created.")

        # 8. Create Evaluations
        for t in trainees:
            TraineeEvaluation.objects.get_or_create(
                trainee=t,
                lecture=lecture1,
                defaults={
                    "evaluator": lecturer_user,
                    "commitment": 9 if t.username == "student1" else 8,
                    "attendance": 10 if t.username != "student4" else 2,
                    "assignments": 9,
                    "participation": 8,
                    "coding": 9 if t.username == "student1" else 7,
                    "projects": 9,
                    "teamwork": 8,
                    "behavior": 10,
                    "communication": 9
                }
            )
        self.stdout.write("Student evaluations created.")

        # 9. Create Projects
        for t in trainees:
            Project.objects.get_or_create(
                trainee=t,
                defaults={
                    "title": "نظام الحجز والطلب الإلكتروني للورش البرمجية",
                    "description": "تطبيق ويب متكامل يتيح للمبرمجين حجز المقاعد للمحاضرات التدريبية وحضورها.",
                    "completion_percentage": 75 if t.username == "student1" else 45,
                    "github_repo": "https://github.com/muntadher/workshop-manager",
                    "demo_url": "https://muntadher-demo.1000programmers.org"
                }
            )
        self.stdout.write("Projects created.")

        # Give badge to student1
        TraineeBadge.objects.get_or_create(trainee=trainees[0], badge=badges[0])
        ActivityPointsLog.objects.get_or_create(
            trainee=trainees[0],
            points=50,
            reason="حصوله على شارة الحضور الكامل لالتزامه الممتاز"
        )
        self.stdout.write("Awarded points and badge to student1.")

        self.stdout.write(self.style.SUCCESS("Database seeded successfully!"))
