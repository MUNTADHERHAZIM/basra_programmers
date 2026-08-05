from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, Http404
from django.utils import timezone
from django.db.models import Avg, Count, Q
from django.views.decorators.http import require_POST
import qrcode
from io import BytesIO
import base64
import json

from apps.users.models import CustomUser, TraineeProfile, LecturerProfile, SupervisorProfile, TraineeNote
from apps.courses.models import Course, Group, Lecture
from apps.attendance.models import Attendance, LectureQRToken
from apps.attendance.services import AttendanceService
from apps.gamification.models import Badge, TraineeBadge, ActivityPointsLog
from apps.assignments.models import Assignment, AssignmentSubmission, Project
from apps.grades.models import TraineeEvaluation, LecturerEvaluation
from apps.certificates.models import Certificate
from apps.certificates.services import CertificateService
from apps.users.services import ImportExportService, LectureGroupImportExportService
from apps.notifications.models import Notification, InternalMessage
from apps.gamification.services import award_points

# ==========================================
# Visitor & Authentication Views
# ==========================================

def landing(request):
    """Public landing page of the 1000 Programmers Initiative."""
    stats = {
        'trainees': TraineeProfile.objects.count(),
        'lecturers': LecturerProfile.objects.count(),
        'supervisors': SupervisorProfile.objects.count(),
        'courses': Course.objects.count(),
        'groups': Group.objects.count(),
    }
    
    # Calculate global attendance rate
    total_att = Attendance.objects.count()
    if total_att > 0:
        present_att = Attendance.objects.filter(status='present').count()
        stats['attendance_rate'] = round((present_att / total_att) * 100, 1)
    else:
        stats['attendance_rate'] = 100.0

    # Get recent announcements
    announcements = InternalMessage.objects.filter(recipient=None, group=None).order_by('-created_at')[:3]
    
    return render(request, 'portal/landing.html', {'stats': stats, 'announcements': announcements})


def login_view(request):
    """Secure login with role redirection."""
    if request.user.is_authenticated:
        return redirect('portal:dashboard')
        
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"أهلاً بك {user.get_full_name() or user.username}!")
            return redirect('portal:dashboard')
        else:
            messages.error(request, "اسم المستخدم أو كلمة المرور غير صحيحة.")
            
    return render(request, 'portal/login.html')


@login_required
def logout_view(request):
    """Logout view."""
    logout(request)
    messages.success(request, "تم تسجيل خروجك بنجاح.")
    return redirect('portal:landing')


@login_required
def dashboard_redirect(request):
    """Redirects the logged-in user to their respective dashboard."""
    role = request.user.role
    if role in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR, CustomUser.Role.TRAINING_OFFICER]:
        return redirect('portal:admin_dashboard')
    elif role == CustomUser.Role.LECTURER:
        return redirect('portal:lecturer_dashboard')
    elif role == CustomUser.Role.SUPERVISOR:
        return redirect('portal:supervisor_dashboard')
    elif role == CustomUser.Role.TRAINEE:
        return redirect('portal:trainee_dashboard')
    else:
        return redirect('portal:landing')

# ==========================================
# Admin / Director Dashboard
# ==========================================

@login_required
def admin_dashboard(request):
    """Dashboard view for Administrator and Director roles."""
    user = request.user
    if user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR, CustomUser.Role.TRAINING_OFFICER]:
        raise Http404("غير مصرح بالدخول.")
        
    # Standard metrics
    stats = {
        'trainees_count': TraineeProfile.objects.count(),
        'lecturers_count': LecturerProfile.objects.count(),
        'supervisors_count': SupervisorProfile.objects.count(),
        'courses_count': Course.objects.count(),
        'groups_count': Group.objects.count(),
        'lectures_done': Lecture.objects.filter(date__lte=timezone.now().date()).count(),
        'lectures_upcoming': Lecture.objects.filter(date__gt=timezone.now().date()).count(),
    }
    
    # Detailed global attendance stats
    total_att = Attendance.objects.count()
    stats['attendance_present'] = Attendance.objects.filter(status='present').count()
    stats['attendance_absent'] = Attendance.objects.filter(status='absent').count()
    stats['attendance_late'] = Attendance.objects.filter(status='late').count()
    stats['attendance_excused'] = Attendance.objects.filter(status='excused').count()
    stats['total_attendance_records'] = total_att

    # Average grades
    avg_grade = TraineeEvaluation.objects.aggregate(avg=Avg('average_grade'))['avg']
    stats['avg_grade'] = round(avg_grade, 2) if avg_grade else 0.0

    # Real University distribution query
    from django.db.models import Count
    import json
    uni_data = (
        TraineeProfile.objects.filter(university__isnull=False)
        .exclude(university='')
        .values('university')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )
    uni_labels = [item['university'] for item in uni_data]
    uni_counts = [item['count'] for item in uni_data]
    
    if not uni_labels:
        uni_labels = ['لا توجد بيانات للجامعات']
        uni_counts = [0]

    # Lists for views
    groups = Group.objects.all().annotate(student_num=Count('trainees'))
    announcements = InternalMessage.objects.filter(recipient=None, group=None).order_by('-created_at')[:5]
    
    context = {
        'stats': stats,
        'groups': groups,
        'announcements': announcements,
        'uni_labels_json': json.dumps(uni_labels),
        'uni_counts_json': json.dumps(uni_counts),
    }
    return render(request, 'portal/admin_dashboard.html', context)

# ==========================================
# Lecturer Dashboard
# ==========================================

@login_required
def lecturer_dashboard(request):
    """Dashboard view for Lecturers."""
    if request.user.role not in [CustomUser.Role.LECTURER, CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        raise Http404("غير مصرح بالدخول.")
        
    if request.user.role in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        groups = Group.objects.all()
    else:
        groups = Group.objects.filter(instructor=request.user)
        if not groups.exists():
            # Fallback if no specific group is assigned to this instructor yet
            groups = Group.objects.all()
        
    # Calculate trainee count
    trainees = TraineeProfile.objects.filter(group__in=groups).select_related('user', 'group')
    
    # Fetch upcoming & completed lectures
    today = timezone.now().date()
    upcoming_lectures = Lecture.objects.filter(group__in=groups, date__gte=today).order_by('date')
    past_lectures = Lecture.objects.filter(group__in=groups, date__lt=today).order_by('-date')
    if not upcoming_lectures.exists() and not past_lectures.exists():
        upcoming_lectures = Lecture.objects.filter(date__gte=today).order_by('date')
        past_lectures = Lecture.objects.filter(date__lt=today).order_by('-date')
    
    # Active assignments
    assignments = Assignment.objects.filter(group__in=groups).order_by('-due_date')
    
    # Daily reports archive
    from apps.courses.models import DailyReport
    daily_reports = DailyReport.objects.filter(group__in=groups).select_related('group', 'lecture').order_by('-created_at')[:10]
    
    # Fetch global/management announcements for lecturers
    from apps.notifications.models import InternalMessage
    announcements = InternalMessage.objects.filter(group__isnull=True).order_by('-created_at')[:5]
    
    context = {
        'groups': groups,
        'trainee_count': trainees.count(),
        'upcoming_lectures': upcoming_lectures,
        'past_lectures': past_lectures,
        'assignments': assignments,
        'trainees': trainees,
        'announcements': announcements,
        'daily_reports': daily_reports,
    }
    return render(request, 'portal/lecturer_dashboard.html', context)

# ==========================================
# Supervisor Dashboard
# ==========================================

@login_required
def supervisor_dashboard(request):
    """Dashboard view for Supervisors."""
    if request.user.role not in [CustomUser.Role.SUPERVISOR, CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        raise Http404("غير مصرح بالدخول.")
        
    if request.user.role in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        supervisor = SupervisorProfile.objects.first().user if SupervisorProfile.objects.exists() else request.user
    else:
        supervisor = request.user
        
    groups = Group.objects.filter(supervisor=supervisor)
    trainees = TraineeProfile.objects.filter(group__in=groups).select_related('user')
    
    # Fetch recent logs / attendance warnings (students with > 3 absences)
    warnings = []
    for trainee in trainees:
        absent_count = Attendance.objects.filter(trainee=trainee.user, status=Attendance.Status.ABSENT).count()
        if absent_count >= 2:
            warnings.append({
                'trainee': trainee,
                'absent_count': absent_count
            })

    context = {
        'groups': groups,
        'trainee_count': trainees.count(),
        'warnings': warnings,
        'trainees': trainees,
    }
    return render(request, 'portal/supervisor_dashboard.html', context)

# ==========================================
# Trainee Dashboard
# ==========================================

@login_required
def trainee_dashboard(request):
    """Dashboard view for Trainees."""
    staff_roles = [
        CustomUser.Role.SUPER_ADMIN,
        CustomUser.Role.DIRECTOR,
        CustomUser.Role.TRAINING_OFFICER,
        CustomUser.Role.SUPERVISOR,
        CustomUser.Role.LECTURER,
    ]
    if request.user.role not in [CustomUser.Role.TRAINEE] + staff_roles:
        raise Http404("غير مصرح بالدخول.")
        
    is_staff_view = request.user.role in staff_roles
    if is_staff_view:
        profile = TraineeProfile.objects.select_related('user', 'group').first()
        if not profile:
            messages.warning(request, "لا يوجد متدربين في النظام للاستعراض حالياً.")
            return redirect('portal:admin_dashboard')
        trainee = profile.user
    else:
        trainee = request.user
        profile, _ = TraineeProfile.objects.get_or_create(user=trainee)
    
    # Leaderboard ranks
    if profile.group:
        group_members = TraineeProfile.objects.filter(group=profile.group).order_by('-points')
    else:
        group_members = TraineeProfile.objects.all().order_by('-points')
    global_members = TraineeProfile.objects.all().order_by('-points')
    
    # Get group rank
    group_rank = 1
    for idx, member in enumerate(group_members, 1):
        if member.user == trainee:
            group_rank = idx
            break
            
    # Get global rank
    global_rank = 1
    for idx, member in enumerate(global_members, 1):
        if member.user == trainee:
            global_rank = idx
            break

    # Stats and records
    attendances = Attendance.objects.filter(trainee=trainee).order_by('-lecture__date')
    evaluations = TraineeEvaluation.objects.filter(trainee=trainee).order_by('-lecture__date')
    
    # Pending assignments
    if profile.group:
        upcoming_assignments = Assignment.objects.filter(group=profile.group, due_date__gt=timezone.now())
    else:
        upcoming_assignments = Assignment.objects.none()
    completed_submissions = AssignmentSubmission.objects.filter(trainee=trainee)
    
    submitted_assignment_ids = completed_submissions.values_list('assignment_id', flat=True)
    pending_assignments = upcoming_assignments.exclude(id__in=submitted_assignment_ids)
    
    # Earned Badges
    badges = TraineeBadge.objects.filter(trainee=trainee).select_related('badge')
    
    # Generated certificates
    certificates = Certificate.objects.filter(trainee=trainee)
    
    # Points log
    from apps.gamification.models import ActivityPointsLog
    points_log = ActivityPointsLog.objects.filter(trainee=trainee).order_by('-id')
    
    # Group leaderboard (top 5)
    group_leaderboard = group_members[:5]
    
    # Fetch targeted and global announcements
    from django.db.models import Q
    from apps.notifications.models import InternalMessage
    if profile.group:
        announcements = InternalMessage.objects.filter(
            Q(group=profile.group) | Q(group__isnull=True)
        ).order_by('-id')
    else:
        announcements = InternalMessage.objects.filter(group__isnull=True).order_by('-id')
    
    # Fetch staff notes with author & timestamp
    from apps.users.models import TraineeNote
    staff_notes = list(TraineeNote.objects.filter(trainee=profile).select_related('author').order_by('-created_at'))
    if not staff_notes and profile.notes:
        note_obj = TraineeNote.objects.create(trainee=profile, author=None, note=profile.notes)
        staff_notes = [note_obj]
        
    context = {
        'profile': profile,
        'group_rank': group_rank,
        'global_rank': global_rank,
        'attendances': attendances,
        'evaluations': evaluations,
        'pending_assignments': pending_assignments,
        'completed_submissions': completed_submissions,
        'badges': badges,
        'certificates': certificates,
        'group': profile.group,
        'points_log': points_log,
        'group_leaderboard': group_leaderboard,
        'announcements': announcements,
        'staff_notes': staff_notes,
        'is_viewing_as_staff': is_staff_view,
    }
    return render(request, 'portal/trainee_dashboard.html', context)

# ==========================================
# Attendance QR Views (HTMX supported)
# ==========================================

@login_required
def lecture_qr_view(request, lecture_id):
    """Lecturer displays dynamic QR code page for students to scan."""
    lecture = get_object_or_404(Lecture, id=lecture_id)
    if request.user.role != CustomUser.Role.LECTURER and request.user.role != CustomUser.Role.SUPER_ADMIN:
        raise Http404("غير مصرح.")
        
    qr_token = AttendanceService.generate_qr_token(lecture.id)
    
    context = {
        'lecture': lecture,
        'token': qr_token.token,
    }
    return render(request, 'portal/lecture_qr.html', context)


@login_required
def get_lecture_qr_token(request, lecture_id):
    """HTMX endpoint to refresh the QR code image tag and token value."""
    lecture = get_object_or_404(Lecture, id=lecture_id)
    if request.user.role != CustomUser.Role.LECTURER and request.user.role != CustomUser.Role.SUPER_ADMIN:
        return HttpResponse("Unauthorized", status=403)
        
    qr_token = AttendanceService.generate_qr_token(lecture.id)
    verify_url = f"{request.build_absolute_uri('/')}portal/verify/{qr_token.token}/" # placeholder or scanning endpoint
    
    # Draw QR code dynamically in HTML
    qr = qrcode.QRCode(version=1, box_size=5, border=1)
    qr.add_data(qr_token.token)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    img_b64 = base64.b64encode(buffer.getvalue()).decode()
    
    html = f'''
    <div id="qr-container" class="text-center" hx-get="/lecture/{lecture.id}/qr/token/" hx-trigger="every 15s" hx-swap="outerHTML">
        <img src="data:image/png;base64,{img_b64}" class="img-fluid border border-dark rounded shadow-lg p-2" style="max-width: 300px;" alt="QR Code">
        <p class="text-muted mt-2"><i class="fas fa-sync fa-spin me-1"></i>يتجدد هذا الكود تلقائياً كل 15 ثانية...</p>
    </div>
    '''
    return HttpResponse(html)


@login_required
def scan_qr_page(request):
    """Trainee opens this page to scan the QR code via webcam."""
    if request.user.role not in [CustomUser.Role.TRAINEE, CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        raise Http404("غير مصرح.")
    return render(request, 'portal/scan_qr.html')


@login_required
@require_POST
def mark_attendance_post(request):
    """Endpoint for handling QR check-ins from trainees' scanner."""
    if request.user.role not in [CustomUser.Role.TRAINEE, CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    try:
        data = json.loads(request.body)
        token = data.get('token')
        lat = data.get('latitude')
        lng = data.get('longitude')
    except (ValueError, KeyError):
        return JsonResponse({'success': False, 'message': 'بيانات غير صالحة.'}, status=400)
        
    success, message = AttendanceService.mark_attendance_via_qr(
        trainee=request.user,
        token_str=token,
        trainee_lat=lat,
        trainee_lng=lng
    )
    
    return JsonResponse({'success': success, 'message': message})

# ==========================================
# Excel Import/Export
# ==========================================

@login_required
def import_trainees_view(request):
    """Handles Excel file uploads for student bulk importing."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR, CustomUser.Role.TRAINING_OFFICER]:
        raise Http404("غير مصرح.")
        
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        group_id = request.POST.get('group_id')
        
        try:
            imported, errors = ImportExportService.import_from_excel(excel_file, group_id)
            if imported > 0:
                messages.success(request, f"تم استيراد {imported} متدرب بنجاح!")
            if errors:
                for error in errors:
                    messages.warning(request, error)
        except Exception as e:
            messages.error(request, f"فشل في قراءة ملف الإكسل: {str(e)}")
            
    return redirect('portal:dashboard')


@login_required
def export_trainees_view(request):
    """Generates and downloads student progress spreadsheets."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR, CustomUser.Role.TRAINING_OFFICER, CustomUser.Role.SUPERVISOR]:
        raise Http404("غير مصرح.")
        
    group_id = request.GET.get('group_id')
    buffer = ImportExportService.export_to_excel(group_id)
    
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="trainees_report.xlsx"'
    return response

# ==========================================
# Google-Calendar-style Schedule View
# ==========================================

@login_required
def calendar_view(request):
    """Displays rich weekly/monthly interactive calendar and daily schedule."""
    user = request.user
    today = timezone.now().date()
    
    # Filter lectures & assignments based on user role
    from apps.assignments.models import Assignment
    from apps.courses.models import Group
    
    if user.role == CustomUser.Role.TRAINEE:
        profile = getattr(user, 'trainee_profile', None)
        user_group = profile.group if profile else None
        if user_group:
            groups = Group.objects.filter(id=user_group.id)
            lectures = Lecture.objects.filter(group=user_group)
            assignments = Assignment.objects.filter(group=user_group)
        else:
            groups = Group.objects.all()
            lectures = Lecture.objects.all()
            assignments = Assignment.objects.all()
    elif user.role == CustomUser.Role.LECTURER:
        user_groups = Group.objects.filter(instructor=user)
        if user_groups.exists():
            groups = user_groups
            lectures = Lecture.objects.filter(group__in=user_groups)
            assignments = Assignment.objects.filter(group__in=user_groups)
        else:
            groups = Group.objects.all()
            lectures = Lecture.objects.all()
            assignments = Assignment.objects.all()
    elif user.role == CustomUser.Role.SUPERVISOR:
        user_groups = Group.objects.filter(supervisor=user)
        if user_groups.exists():
            groups = user_groups
            lectures = Lecture.objects.filter(group__in=user_groups)
            assignments = Assignment.objects.filter(group__in=user_groups)
        else:
            groups = Group.objects.all()
            lectures = Lecture.objects.all()
            assignments = Assignment.objects.all()
    else:
        groups = Group.objects.all()
        lectures = Lecture.objects.all()
        assignments = Assignment.objects.all()
        
    events = []
    # 1. Format Lectures for Calendar
    for lec in lectures.select_related('group', 'group__course', 'group__instructor'):
        events.append({
            'id': f"lec-{lec.id}",
            'type': 'lecture',
            'title': f"📚 {lec.title}",
            'course': lec.group.course.title if (lec.group and lec.group.course) else "مادة عامة",
            'group_name': lec.group.name if lec.group else "عامة",
            'date': lec.date.isoformat(),
            'start_time': lec.start_time.strftime('%H:%M'),
            'end_time': lec.end_time.strftime('%H:%M'),
            'classroom': lec.group.classroom if lec.group else "قاعة التدريب",
            'instructor': (lec.group.instructor.get_full_name() or lec.group.instructor.username) if (lec.group and lec.group.instructor) else "غير محدد",
            'color': '#10b981',
            'badge': 'محاضرة تدريبية',
        })
        
    # 2. Format Assignments for Calendar
    for asg in assignments.select_related('group', 'group__course'):
        events.append({
            'id': f"asg-{asg.id}",
            'type': 'assignment',
            'title': f"📝 تسليم واجب: {asg.title}",
            'course': asg.group.course.title if (asg.group and asg.group.course) else "واجب مادة",
            'group_name': asg.group.name if asg.group else "شعبة",
            'date': asg.due_date.date().isoformat(),
            'start_time': asg.due_date.strftime('%H:%M'),
            'end_time': asg.due_date.strftime('%H:%M'),
            'classroom': "تسليم إلكتروني عبر المنصة",
            'instructor': "المحاضر المصحح",
            'color': '#ef4444',
            'badge': 'موعد تسليم واجب',
        })
        
    # 3. Weekly Schedule Grid Data by Days
    days_order = ['الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'السبت', 'الجمعة']
    weekly_schedule = {day: [] for day in days_order}
    
    class ScheduleItem:
        def __init__(self, group, title=None, start_time=None, end_time=None):
            self.group = group
            self.title = title or (group.course.title if group.course else group.name)
            self.start_time = start_time or group.start_time
            self.end_time = end_time or group.end_time
            self.classroom = group.classroom
            
    # Add recurring Group schedule items
    for g in groups.select_related('course', 'instructor'):
        if g.days:
            group_days = [d.strip() for d in g.days.replace('،', ',').split(',') if d.strip()]
            for day in group_days:
                matched_day = None
                for d_name in days_order:
                    if d_name in day or day in d_name:
                        matched_day = d_name
                        break
                if matched_day and matched_day in weekly_schedule:
                    weekly_schedule[matched_day].append(ScheduleItem(g))
                    
    # Add specific lectures if present
    for lec in lectures.select_related('group', 'group__course', 'group__instructor'):
        if lec.group and lec.group.days:
            group_days = [d.strip() for d in lec.group.days.replace('،', ',').split(',') if d.strip()]
            for day in group_days:
                matched_day = None
                for d_name in days_order:
                    if d_name in day or day in d_name:
                        matched_day = d_name
                        break
                if matched_day and matched_day in weekly_schedule:
                    weekly_schedule[matched_day].append(ScheduleItem(lec.group, title=lec.title, start_time=lec.start_time, end_time=lec.end_time))
                    
    # Summary Metrics
    today_lectures = [e for e in events if e['type'] == 'lecture' and e['date'] == today.isoformat()]
    upcoming_assignments_count = len([e for e in events if e['type'] == 'assignment' and e['date'] >= today.isoformat()])
    
    total_schedule_items = sum(len(items) for items in weekly_schedule.values())
    total_events_count = len(events) or total_schedule_items
    
    context = {
        'events': events,
        'weekly_schedule': weekly_schedule,
        'today_lectures_count': len(today_lectures),
        'upcoming_assignments_count': upcoming_assignments_count,
        'total_events_count': total_events_count,
    }
    return render(request, 'portal/calendar.html', context)

# ==========================================
# Public Verification Page
# ==========================================

def verify_certificate(request, token):
    """Publicly verify a generated certificate by its unique verification token."""
    cert = get_object_or_404(Certificate, verification_token=token)
    return render(request, 'portal/verify_certificate.html', {'certificate': cert})

# ==========================================
# Assignments, Projects & Grades Views
# ==========================================

@login_required
def create_assignment_view(request, group_id):
    """Allows instructors to publish a new assignment."""
    if request.user.role not in [CustomUser.Role.LECTURER, CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        raise Http404()
        
    group = Group.objects.filter(id=group_id, instructor=request.user).first()
    if not group:
        group = get_object_or_404(Group, id=group_id)
        
    if request.method == 'POST':
        title = request.POST.get('title')
        desc = request.POST.get('description')
        due = request.POST.get('due_date')
        file = request.FILES.get('file')
        
        Assignment.objects.create(
            group=group,
            title=title,
            description=desc,
            due_date=due,
            file=file
        )
        messages.success(request, "تم نشر الواجب الدراسي بنجاح.")
        return redirect('portal:lecturer_dashboard')
        
    return render(request, 'portal/create_assignment.html', {'group': group})


@login_required
def submit_assignment_view(request, assignment_id):
    """Allows students to submit a homework with text, files, images, or video uploads/links."""
    if request.user.role not in [CustomUser.Role.TRAINEE, CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        raise Http404()
        
    assignment = get_object_or_404(Assignment, id=assignment_id)
    submission = AssignmentSubmission.objects.filter(assignment=assignment, trainee=request.user).first()

    if request.method == 'POST':
        submission_text = request.POST.get('submission_text', '').strip()
        video_url = request.POST.get('video_url', '').strip()
        solution_file = request.FILES.get('solution_file')
        submission_image = request.FILES.get('submission_image')
        video_file = request.FILES.get('video_file')
        
        if not (submission_text or solution_file or submission_image or video_file or video_url):
            messages.error(request, "يرجى إضافة إجابة نصية، صورة، فيديو، أو ملف مرفق لتسليم الواجب.")
            return render(request, 'portal/submit_assignment.html', {'assignment': assignment, 'submission': submission})

        defaults = {'submitted_at': timezone.now()}
        if submission_text:
            defaults['submission_text'] = submission_text
        if video_url:
            defaults['video_url'] = video_url
        if solution_file:
            defaults['file'] = solution_file
        if submission_image:
            defaults['image'] = submission_image
        if video_file:
            defaults['video_file'] = video_file

        sub, created = AssignmentSubmission.objects.update_or_create(
            assignment=assignment,
            trainee=request.user,
            defaults=defaults
        )
        
        # Award points for submission if created
        if created:
            award_points(request.user, 15, f"تسليم الواجب الدراسي: '{assignment.title}'")
            messages.success(request, "تم تسليم الواجب الدراسي وإضافة نقاط المبادرة بنجاح!")
        else:
            messages.success(request, "تم تحديث تسليم الواجب بنجاح!")

        return redirect('portal:trainee_dashboard')
        
    return render(request, 'portal/submit_assignment.html', {'assignment': assignment, 'submission': submission})


@login_required
def grade_submission_view(request, submission_id):
    """Allows instructors to correct a student's solution."""
    if request.user.role not in [CustomUser.Role.LECTURER, CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        raise Http404()
        
    submission = AssignmentSubmission.objects.filter(id=submission_id, assignment__group__instructor=request.user).first()
    if not submission:
        submission = get_object_or_404(AssignmentSubmission, id=submission_id)
    
    if request.method == 'POST':
        grade = int(request.POST.get('grade', 0))
        feedback = request.POST.get('feedback', '')
        
        submission.grade = grade
        submission.feedback = feedback
        submission.graded_by = request.user
        submission.save()
        
        # Award points based on performance
        if grade >= 9:
            award_points(submission.trainee, 20, f"التميز البرمجي في واجب '{submission.assignment.title}' (الدرجة {grade}/10)")
        elif grade >= 7:
            award_points(submission.trainee, 10, f"اجتياز واجب '{submission.assignment.title}' (الدرجة {grade}/10)")
            
        messages.success(request, "تم تسجيل درجة الواجب وإرسال التغذية الراجعة.")
        return redirect('portal:lecturer_dashboard')
        
    return render(request, 'portal/grade_submission.html', {'submission': submission})


@login_required
def evaluate_students_view(request, lecture_id):
    """Enables instructors to evaluate student performance for a past lecture."""
    if request.user.role not in [CustomUser.Role.LECTURER, CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        raise Http404()
        
    lecture = Lecture.objects.filter(id=lecture_id, group__instructor=request.user).first()
    if not lecture:
        lecture = get_object_or_404(Lecture, id=lecture_id)
    trainees = TraineeProfile.objects.filter(group=lecture.group).select_related('user')
    
    if request.method == 'POST':
        # Batch save evaluations
        for trainee in trainees:
            t_id = trainee.user.id
            commitment = request.POST.get(f'commitment_{t_id}', 10)
            attendance = request.POST.get(f'attendance_{t_id}', 10)
            assignments = request.POST.get(f'assignments_{t_id}', 10)
            participation = request.POST.get(f'participation_{t_id}', 10)
            coding = request.POST.get(f'coding_{t_id}', 10)
            projects = request.POST.get(f'projects_{t_id}', 10)
            teamwork = request.POST.get(f'teamwork_{t_id}', 10)
            behavior = request.POST.get(f'behavior_{t_id}', 10)
            communication = request.POST.get(f'communication_{t_id}', 10)
            notes = request.POST.get(f'notes_{t_id}', '')
            
            TraineeEvaluation.objects.update_or_create(
                trainee=trainee.user,
                lecture=lecture,
                defaults={
                    'evaluator': request.user,
                    'commitment': int(commitment),
                    'attendance': int(attendance),
                    'assignments': int(assignments),
                    'participation': int(participation),
                    'coding': int(coding),
                    'projects': int(projects),
                    'teamwork': int(teamwork),
                    'behavior': int(behavior),
                    'communication': int(communication),
                    'notes': notes
                }
            )
        messages.success(request, "تم حفظ تقييمات الطلاب بنجاح.")
        return redirect('portal:lecturer_dashboard')
        
    # Get existing evaluations to pre-populate form
    evaluations_dict = {
        eval.trainee_id: eval for eval in TraineeEvaluation.objects.filter(lecture=lecture)
    }
    
    context = {
        'lecture': lecture,
        'trainees': trainees,
        'evaluations': evaluations_dict
    }
    return render(request, 'portal/evaluate_students.html', context)


@login_required
def evaluate_lecturer_view(request, lecture_id):
    """Enables trainees to grade the instructor after a lecture."""
    if request.user.role not in [CustomUser.Role.TRAINEE, CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        raise Http404()
        
    if request.user.role in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        lecture = get_object_or_404(Lecture, id=lecture_id)
    else:
        lecture = get_object_or_404(Lecture, id=lecture_id, group__trainees__user=request.user)
    
    if request.method == 'POST':
        clarity = int(request.POST.get('clarity', 5))
        commitment = int(request.POST.get('commitment', 5))
        quality = int(request.POST.get('quality', 5))
        interaction = int(request.POST.get('interaction', 5))
        time = int(request.POST.get('time', 5))
        notes = request.POST.get('notes', '')
        
        LecturerEvaluation.objects.update_or_create(
            lecture=lecture,
            trainee=request.user,
            defaults={
                'lecturer': lecture.group.instructor,
                'explanation_clarity': clarity,
                'commitment': commitment,
                'material_quality': quality,
                'interaction': interaction,
                'time_management': time,
                'notes': notes
            }
        )
        
        # Award student points for reviewing the lecturer
        award_points(request.user, 5, f"تقديم تقييم المحاضر لمحاضرة '{lecture.title}'")
        
        messages.success(request, "نشكرك على تقييم المحاضر! تم إضافة 5 نقاط في رصيدك.")
        return redirect('portal:trainee_dashboard')
        
    return render(request, 'portal/evaluate_lecturer.html', {'lecture': lecture})


@login_required
def activity_log_view(request):
    """Unified Activity Feed & Logging Page for Admins and Directors."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        raise Http404("غير مصرح بالدخول.")

    # 1. Points Logs (Activities)
    points_logs = ActivityPointsLog.objects.select_related('trainee').order_by('-created_at')[:50]
    
    # 2. Attendance Records
    attendance_logs = Attendance.objects.select_related('trainee', 'lecture', 'lecture__group').order_by('-check_in_time')[:50]
    
    # 3. Evaluations & Instructor Notes
    evaluation_logs = TraineeEvaluation.objects.select_related('trainee', 'lecture', 'evaluator').order_by('-id')[:50]
    
    # 4. Homework Submissions
    submissions_logs = AssignmentSubmission.objects.select_related('trainee', 'assignment', 'assignment__group').order_by('-submitted_at')[:50]

    context = {
        'points_logs': points_logs,
        'attendance_logs': attendance_logs,
        'evaluation_logs': evaluation_logs,
        'submissions_logs': submissions_logs,
    }
    return render(request, 'portal/activity_log.html', context)


@login_required
def mark_attendance_manual_view(request, lecture_id):
    """Allows instructors to manually mark trainee attendance for a lecture."""
    if request.user.role not in [CustomUser.Role.LECTURER, CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        raise Http404("غير مصرح بالدخول.")
        
    lecture = Lecture.objects.filter(id=lecture_id, group__instructor=request.user).first()
    if not lecture:
        lecture = get_object_or_404(Lecture, id=lecture_id)
        
    trainees = TraineeProfile.objects.filter(group=lecture.group).select_related('user')
    if not trainees.exists():
        trainees = TraineeProfile.objects.all().select_related('user')
    
    if request.method == 'POST':
        for trainee in trainees:
            t_id = trainee.user.id
            status = request.POST.get(f'status_{t_id}', 'absent')
            delay_val = request.POST.get(f'delay_{t_id}', 0)
            notes_val = request.POST.get(f'notes_{t_id}', '')
            
            # Update or create attendance record
            att, created = Attendance.objects.update_or_create(
                trainee=trainee.user,
                lecture=lecture,
                defaults={
                    'status': status,
                    'method': Attendance.Method.MANUAL,
                    'check_in_time': timezone.now() if status in ['present', 'late'] else None,
                    'delay_minutes': int(delay_val) if delay_val and status == 'late' else 0,
                    'notes': notes_val.strip() if notes_val else None,
                }
            )
            
            # Award/adjust points based on manual marking
            if status == 'present':
                award_points(trainee.user, 10, f"حضور محاضرة: '{lecture.title}' (تسجيل يدوي)")
            elif status == 'late':
                award_points(trainee.user, 5, f"حضور متأخر لمحاضرة: '{lecture.title}' (تسجيل يدوي)")
                
        messages.success(request, "تم تسجيل وتحديث حضور الطلاب يدوياً بنجاح.")
        return redirect('portal:lecturer_dashboard')
        
    # Pre-populate existing attendances
    attendances_qs = Attendance.objects.filter(lecture=lecture)
    existing_attendance = {att.trainee_id: att.status for att in attendances_qs}
    existing_notes = {att.trainee_id: att.notes for att in attendances_qs}
    existing_delays = {att.trainee_id: att.delay_minutes for att in attendances_qs}
    
    context = {
        'lecture': lecture,
        'trainees': trainees,
        'existing_attendance': existing_attendance,
        'existing_notes': existing_notes,
        'existing_delays': existing_delays,
    }
    return render(request, 'portal/mark_attendance_manual.html', context)


@login_required
def admin_management_hub(request):
    """Unified HTML portal management dashboard for Admin to manage Lecturers, Trainees, Groups, and Lectures."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        raise Http404("غير مصرح بالدخول.")
        
    lecturers = CustomUser.objects.filter(role=CustomUser.Role.LECTURER).prefetch_related('lecturer_profile')
    trainees = TraineeProfile.objects.select_related('user', 'group').all()
    groups = Group.objects.select_related('course', 'instructor', 'supervisor').all()
    lectures = Lecture.objects.select_related('group', 'group__course').order_by('-date')
    courses = Course.objects.all()
    badges = Badge.objects.all()
    certificates = Certificate.objects.select_related('trainee', 'course').all()
    announcements = InternalMessage.objects.filter(recipient=None, group=None).order_by('-created_at')
    
    # Supervisors lists to populate supervisor dropdowns
    supervisors = CustomUser.objects.filter(role=CustomUser.Role.SUPERVISOR)
    
    # Prepare weekly training schedule data dynamically
    days_map = [
        {'name': 'السبت', 'keywords': ['السبت', 'saturday', 'sat']},
        {'name': 'الأحد', 'keywords': ['أحد', 'احد', 'sunday', 'sun']},
        {'name': 'الإثنين', 'keywords': ['إثنين', 'اثنين', 'monday', 'mon']},
        {'name': 'الثلاثاء', 'keywords': ['ثلاثاء', 'tuesday', 'tue']},
        {'name': 'الأربعاء', 'keywords': ['أربعاء', 'اربعاء', 'wednesday', 'wed']},
        {'name': 'الخميس', 'keywords': ['خميس', 'thursday', 'thu']},
        {'name': 'الجمعة', 'keywords': ['جمعة', 'جمعه', 'friday', 'fri']},
    ]
    schedule_data = {d['name']: [] for d in days_map}
    for g in groups:
        if g.days:
            days_str = g.days.lower()
            for d in days_map:
                if any(kw in days_str for kw in d['keywords']):
                    schedule_data[d['name']].append(g)
                    
    context = {
        'lecturers': lecturers,
        'trainees': trainees,
        'groups': groups,
        'lectures': lectures,
        'courses': courses,
        'supervisors': supervisors,
        'badges': badges,
        'certificates': certificates,
        'announcements': announcements,
        'schedule_data': schedule_data,
    }
    return render(request, 'portal/admin_management_hub.html', context)


@login_required
@require_POST
def add_lecturer_post(request):
    """Saves a new lecturer user account from HTML form."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    username = request.POST.get('username')
    email = request.POST.get('email', '')
    first_name = request.POST.get('first_name')
    last_name = request.POST.get('last_name')
    specialty = request.POST.get('specialty', '')
    bio = request.POST.get('bio', '')
    
    if not username:
        messages.error(request, "اسم المستخدم حقل مطلوب.")
        return redirect('portal:admin_management_hub')
        
    try:
        user = CustomUser.objects.create_user(
            username=username.strip(),
            email=email.strip() if email else f"{username.strip()}@1000programmers.iq",
            first_name=first_name.strip() if first_name else '',
            last_name=last_name.strip() if last_name else '',
            role=CustomUser.Role.LECTURER,
            password="Password123"
        )
        LecturerProfile.objects.create(
            user=user,
            specialty=specialty,
            bio=bio
        )
        messages.success(request, f"تم إنشاء حساب المحاضر {user.get_full_name() or user.username} بنجاح. كلمة المرور الافتراضية: Password123")
    except Exception as e:
        messages.error(request, f"فشل إنشاء الحساب: {str(e)}")
        
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def add_trainee_post(request):
    """Saves a new trainee user account and profile from HTML form."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    username = request.POST.get('username')
    email = request.POST.get('email', '')
    first_name = request.POST.get('first_name')
    last_name = request.POST.get('last_name')
    group_id = request.POST.get('group')
    gov = request.POST.get('governorate', 'البصرة')
    dist = request.POST.get('district', '')
    uni = request.POST.get('university', '')
    col = request.POST.get('college', '')
    dept = request.POST.get('department', '')
    stage = request.POST.get('academic_stage', '')
    spec = request.POST.get('specialty', '')
    
    if not username:
        messages.error(request, "اسم المستخدم حقل مطلوب.")
        return redirect('portal:admin_management_hub')
        
    try:
        group = None
        if group_id:
            group = Group.objects.get(id=group_id)
            
        user = CustomUser.objects.create_user(
            username=username.strip(),
            email=email.strip() if email else f"{username.strip()}@1000programmers.iq",
            first_name=first_name.strip() if first_name else '',
            last_name=last_name.strip() if last_name else '',
            role=CustomUser.Role.TRAINEE,
            password="Password123"
        )
        TraineeProfile.objects.create(
            user=user,
            group=group,
            governorate=gov,
            district=dist,
            university=uni,
            college=col,
            department=dept,
            academic_stage=stage,
            specialty=spec
        )
        messages.success(request, f"تم تسجيل المتدرب {user.get_full_name() or user.username} بنجاح. كلمة المرور الافتراضية: Password123")
    except Exception as e:
        messages.error(request, f"فشل تسجيل المتدرب: {str(e)}")
        
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def add_group_post(request):
    """Saves a new group from HTML form."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    schedule_type = request.POST.get('schedule_type', 'new')
    group_id = request.POST.get('group_id')
    name = request.POST.get('name')
    course_id = request.POST.get('course')
    course_title = request.POST.get('course_title', '').strip()
    instructor_id = request.POST.get('instructor')
    supervisor_id = request.POST.get('supervisor')
    classroom = request.POST.get('classroom')
    code = request.POST.get('code')
    days_list = request.POST.getlist('days')
    days = "، ".join(days_list) if days_list else request.POST.get('days', '')
    start_time = request.POST.get('start_time')
    end_time = request.POST.get('end_time')
    
    try:
        # Resolve course/subject dynamically
        course = None
        if course_title:
            course, _ = Course.objects.get_or_create(
                title=course_title,
                defaults={'hours': 60, 'description': f"مادة {course_title}"}
            )
        elif course_id:
            course = Course.objects.get(id=course_id)
            
        if schedule_type == 'existing' and group_id:
            group = Group.objects.get(id=group_id)
            if name: group.name = name.strip()
            if course: group.course = course
            group.instructor = CustomUser.objects.get(id=instructor_id) if instructor_id else None
            group.supervisor = CustomUser.objects.get(id=supervisor_id) if supervisor_id else None
            if classroom: group.classroom = classroom.strip()
            if code: group.code = code.strip()
            if days: group.days = days.strip()
            if start_time: group.start_time = start_time
            if end_time: group.end_time = end_time
            group.save()
            messages.success(request, f"تم تحديث جدولة الشعبة '{group.name}' بنجاح.")
        else:
            if not name or not course:
                messages.error(request, "اسم الشعبة والمادة حقول مطلوبة.")
                return redirect('portal:admin_management_hub')
                
            instructor = CustomUser.objects.get(id=instructor_id) if instructor_id else None
            supervisor = CustomUser.objects.get(id=supervisor_id) if supervisor_id else None
            
            if not code or not code.strip():
                import random
                clean_title = "".join([c for c in course.title if c.isalnum()])[:3].upper()
                code = f"{clean_title}-{random.randint(100, 999)}"
                
            group = Group.objects.create(
                name=name.strip(),
                code=code.strip(),
                course=course,
                instructor=instructor,
                supervisor=supervisor,
                classroom=classroom.strip() if classroom else 'قاعة عامة',
                days=days.strip() if days else 'الأحد، الثلاثاء، الخميس',
                start_time=start_time if start_time else '16:00',
                end_time=end_time if end_time else '18:00'
            )
            messages.success(request, f"تم إنشاء وجدولة الشعبة الجديدة '{group.name}' بنجاح.")
    except Exception as e:
        messages.error(request, f"فشل العملية: {str(e)}")
        
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def add_lecture_post(request):
    """Saves a new lecture from HTML form."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    title = request.POST.get('title')
    group_id = request.POST.get('group')
    date_val = request.POST.get('date')
    start_time = request.POST.get('start_time')
    end_time = request.POST.get('end_time')
    location = request.POST.get('location')
    
    if not title or not group_id or not date_val:
        messages.error(request, "عنوان المحاضرة والمجموعة والتاريخ حقول مطلوبة.")
        return redirect('portal:admin_management_hub')
        
    try:
        group = Group.objects.get(id=group_id)
        lecture = Lecture.objects.create(
            title=title.strip(),
            group=group,
            date=date_val,
            start_time=start_time,
            end_time=end_time
        )
        messages.success(request, f"تمت إضافة محاضرة '{lecture.title}' بنجاح.")
    except Exception as e:
        messages.error(request, f"فشل إضافة المحاضرة: {str(e)}")
        
    return redirect('portal:admin_management_hub')


@login_required
def export_groups_view(request):
    """Exports all groups to an Excel sheet."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        raise Http404("غير مصرح.")
    buffer = LectureGroupImportExportService.export_groups()
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="groups_export.xlsx"'
    return response


@login_required
@require_POST
def import_groups_view(request):
    """Imports groups from an Excel sheet."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    if request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        try:
            imported, errors = LectureGroupImportExportService.import_groups(excel_file)
            if imported > 0:
                messages.success(request, f"تم استيراد {imported} شعبة/مجموعة بنجاح!")
            if errors:
                for error in errors:
                    messages.warning(request, error)
        except Exception as e:
            messages.error(request, f"فشل الاستيراد: {str(e)}")
            
    return redirect('portal:admin_management_hub')


@login_required
def export_lectures_view(request):
    """Exports all lectures to an Excel sheet."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        raise Http404("غير مصرح.")
    buffer = LectureGroupImportExportService.export_lectures()
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="lectures_export.xlsx"'
    return response


@login_required
@require_POST
def import_lectures_view(request):
    """Imports lectures from an Excel sheet."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    if request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        try:
            imported, errors = LectureGroupImportExportService.import_lectures(excel_file)
            if imported > 0:
                messages.success(request, f"تم استيراد {imported} محاضرة بنجاح!")
            if errors:
                for error in errors:
                    messages.warning(request, error)
        except Exception as e:
            messages.error(request, f"فشل الاستيراد: {str(e)}")
            
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def add_course_post(request):
    """Saves a new course from HTML form."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
    title = request.POST.get('title')
    description = request.POST.get('description', '')
    hours = request.POST.get('hours', 60)
    if title:
        try:
            Course.objects.create(
                title=title.strip(),
                description=description.strip(),
                hours=int(hours) if hours else 60
            )
            messages.success(request, f"تمت إضافة الدورة '{title}' بنجاح.")
        except Exception as e:
            messages.error(request, f"فشل إضافة الدورة: {str(e)}")
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def edit_course_post(request, course_id):
    """Updates an existing course details."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
    course = get_object_or_404(Course, id=course_id)
    title = request.POST.get('title')
    description = request.POST.get('description', '')
    hours = request.POST.get('hours', 60)
    
    if title:
        try:
            course.title = title.strip()
            course.description = description.strip()
            course.hours = int(hours) if hours else 60
            course.save()
            messages.success(request, "تم تحديث الدورة التدريبية بنجاح.")
        except Exception as e:
            messages.error(request, f"فشل تحديث الدورة: {str(e)}")
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def delete_course_post(request, course_id):
    """Deletes an existing course."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
    course = get_object_or_404(Course, id=course_id)
    try:
        title = course.title
        course.delete()
        messages.success(request, f"تم حذف الدورة '{title}' بنجاح.")
    except Exception as e:
        messages.error(request, f"فشل حذف الدورة: {str(e)}")
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def add_badge_post(request):
    """Saves a new gamified badge from HTML form."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
    title = request.POST.get('title')
    points = request.POST.get('points_required', 100)
    icon = request.POST.get('icon', 'award')
    description = request.POST.get('description', '')
    if title:
        try:
            Badge.objects.create(
                name=title.strip(),
                points_required=int(points) if points else 100,
                icon_name=icon,
                description=description.strip()
            )
            messages.success(request, f"تم إنشاء الشارة '{title}' بنجاح.")
        except Exception as e:
            messages.error(request, f"فشل إنشاء الشارة: {str(e)}")
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def award_badge_post(request):
    """Awards a specific badge to a trainee manually from HTML form."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
    trainee_id = request.POST.get('trainee')
    badge_id = request.POST.get('badge')
    if trainee_id and badge_id:
        try:
            trainee_user = get_object_or_404(CustomUser, id=trainee_id)
            badge = get_object_or_404(Badge, id=badge_id)
            
            # Grant ONLY this specific badge
            t_badge, created = TraineeBadge.objects.get_or_create(trainee=trainee_user, badge=badge)
            
            # Safely log activity points for this badge without cascading
            from apps.gamification.models import ActivityPointsLog
            ActivityPointsLog.objects.create(
                trainee=trainee_user,
                points=badge.points_required,
                reason=f"الحصول على شارة التميز: {badge.name}"
            )
            prof = getattr(trainee_user, 'trainee_profile', None)
            if prof:
                prof.points += badge.points_required
                prof.save()
                
            messages.success(request, f"تم منح الشارة '{badge.name}' للمتدرب {trainee_user.get_full_name() or trainee_user.username} بنجاح.")
        except Exception as e:
            messages.error(request, f"فشل منح الشارة: {str(e)}")
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def generate_certificate_post(request):
    """Generates a Graduation Certificate PDF and database entry for a student."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
    trainee_id = request.POST.get('trainee')
    course_id = request.POST.get('course')
    if trainee_id and course_id:
        try:
            trainee_user = get_object_or_404(CustomUser, id=trainee_id)
            course = get_object_or_404(Course, id=course_id)
            cert, created = Certificate.objects.get_or_create(
                trainee=trainee_user,
                course=course
            )
            # Pass the current live domain so that the verification QR code works perfectly!
            domain = request.build_absolute_uri('/')[:-1]
            CertificateService.generate_pdf(cert.id, domain=domain)
            messages.success(request, f"تم إصدار وتوليد الشهادة الرقمية للمتدرب {trainee_user.get_full_name() or trainee_user.username} بنجاح!")
        except Exception as e:
            messages.error(request, f"فشل إصدار الشهادة: {str(e)}")
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def add_announcement_post(request):
    """Saves a new global or targeted broadcast announcement from HTML form."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
    title = request.POST.get('title')
    body = request.POST.get('body')
    target_audience = request.POST.get('target_audience', 'all')
    group_id = request.POST.get('group_id')
    
    if title and body:
        try:
            full_content = f"{title.strip()}\n\n{body.strip()}"
            
            target_group = None
            users_to_notify = []
            
            if target_audience == 'group' and group_id:
                target_group = get_object_or_404(Group, id=group_id)
                users_to_notify = CustomUser.objects.filter(role=CustomUser.Role.TRAINEE, trainee_profile__group=target_group)
                audience_desc = f"شعبة {target_group.name}"
            elif target_audience == 'trainees':
                users_to_notify = CustomUser.objects.filter(role=CustomUser.Role.TRAINEE)
                audience_desc = "جميع الطلاب"
            elif target_audience == 'lecturers':
                users_to_notify = CustomUser.objects.filter(role=CustomUser.Role.LECTURER)
                audience_desc = "جميع المدربين"
            else: # all
                users_to_notify = CustomUser.objects.filter(role__in=[CustomUser.Role.TRAINEE, CustomUser.Role.LECTURER])
                audience_desc = "جميع منتسبي المبادرة (مدربين وطلاب)"
                
            InternalMessage.objects.create(
                sender=request.user,
                content=full_content,
                recipient=None,
                group=target_group
            )
            
            from apps.notifications.models import Notification
            for u in users_to_notify:
                Notification.objects.create(
                    user=u,
                    title=title.strip(),
                    message=body.strip()[:200]
                )
                
            messages.success(request, f"تم نشر وبث الإعلان لـ ({audience_desc}) بنجاح!")
        except Exception as e:
            messages.error(request, f"فشل نشر الإعلان: {str(e)}")
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def update_site_config_post(request):
    """Updates general site configuration (logo, name, subtitle) from HTML form."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
    site_name = request.POST.get('site_name')
    sub_title = request.POST.get('sub_title')
    logo = request.FILES.get('logo')
    
    try:
        config = SiteConfiguration.objects.first()
        if not config:
            config = SiteConfiguration.objects.create()
        if site_name:
            config.site_name = site_name.strip()
        if sub_title:
            config.sub_title = sub_title.strip()
        if logo:
            config.logo = logo
        config.save()
        messages.success(request, "تم تحديث إعدادات وشعار المنصة بنجاح.")
    except Exception as e:
        messages.error(request, f"فشل تحديث الإعدادات: {str(e)}")
    return redirect('portal:admin_management_hub')


@login_required
def edit_profile_view(request):
    """Allows any logged-in user to update their name/email, role-specific profile details, and change their password."""
    user = request.user
    
    # Initialize profiles
    lecturer_profile = None
    trainee_profile = None
    
    if user.role == CustomUser.Role.LECTURER:
        lecturer_profile, _ = LecturerProfile.objects.get_or_create(user=user)
    elif user.role == CustomUser.Role.TRAINEE:
        trainee_profile, _ = TraineeProfile.objects.get_or_create(user=user)
        
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Action 1: Update personal info
        if action == 'update_info':
            first_name = request.POST.get('first_name', '')
            last_name = request.POST.get('last_name', '')
            email = request.POST.get('email', '')
            
            user.first_name = first_name.strip()
            user.last_name = last_name.strip()
            if email:
                user.email = email.strip()
            user.save()
            
            if user.role == CustomUser.Role.LECTURER and lecturer_profile:
                lecturer_profile.specialty = request.POST.get('specialty', '')
                lecturer_profile.bio = request.POST.get('bio', '')
                lecturer_profile.save()
            elif user.role == CustomUser.Role.TRAINEE and trainee_profile:
                trainee_profile.university = request.POST.get('university', '')
                trainee_profile.college = request.POST.get('college', '')
                trainee_profile.department = request.POST.get('department', '')
                trainee_profile.academic_stage = request.POST.get('academic_stage', '')
                trainee_profile.specialty = request.POST.get('specialty', '')
                trainee_profile.governorate = request.POST.get('governorate', 'البصرة')
                trainee_profile.district = request.POST.get('district', '')
                trainee_profile.save()
                
            messages.success(request, "تم تحديث بيانات الملف الشخصي بنجاح.")
            return redirect('portal:edit_profile')
            
        # Action 2: Change password
        elif action == 'change_password':
            old_password = request.POST.get('old_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            if not user.check_password(old_password):
                messages.error(request, "كلمة المرور الحالية غير صحيحة.")
            elif new_password != confirm_password:
                messages.error(request, "تأكيد كلمة المرور الجديدة غير متطابق.")
            elif len(new_password) < 6:
                messages.error(request, "كلمة المرور الجديدة يجب أن لا تقل عن 6 أحرف/أرقام.")
            else:
                user.set_password(new_password)
                user.save()
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, user) # Keeps user logged in
                messages.success(request, "تم تغيير كلمة المرور بنجاح!")
                return redirect('portal:edit_profile')
                
    context = {
        'lecturer_profile': lecturer_profile,
        'trainee_profile': trainee_profile,
    }
    return render(request, 'portal/edit_profile.html', context)


@login_required
def view_trainee_profile_detail(request, trainee_user_id):
    """Allows admins, directors, supervisors, and lecturers to view a specific student's profile/dashboard."""
    # Check permissions
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR, CustomUser.Role.SUPERVISOR, CustomUser.Role.LECTURER, CustomUser.Role.TRAINEE]:
        raise Http404("غير مصرح بالدخول.")
        
    # Trainees can only view their own profile detail
    if request.user.role == CustomUser.Role.TRAINEE and request.user.id != trainee_user_id:
        raise Http404("غير مصرح بالدخول.")
        
    trainee = get_object_or_404(CustomUser, id=trainee_user_id, role=CustomUser.Role.TRAINEE)
    profile = get_object_or_404(TraineeProfile, user=trainee)
    
    # Leaderboard ranks
    group_members = TraineeProfile.objects.filter(group=profile.group).order_by('-points')
    global_members = TraineeProfile.objects.all().order_by('-points')
    
    # Get group rank
    group_rank = 1
    for idx, member in enumerate(group_members, 1):
        if member.user == trainee:
            group_rank = idx
            break
            
    # Get global rank
    global_rank = 1
    for idx, member in enumerate(global_members, 1):
        if member.user == trainee:
            global_rank = idx
            break
            
    # Stats and records
    attendances = Attendance.objects.filter(trainee=trainee).order_by('-lecture__date')
    evaluations = TraineeEvaluation.objects.filter(trainee=trainee).order_by('-lecture__date')
    
    # Pending assignments
    upcoming_assignments = Assignment.objects.filter(group=profile.group, due_date__gt=timezone.now())
    completed_submissions = AssignmentSubmission.objects.filter(trainee=trainee)
    
    submitted_assignment_ids = completed_submissions.values_list('assignment_id', flat=True)
    pending_assignments = upcoming_assignments.exclude(id__in=submitted_assignment_ids)
    
    # Earned Badges
    badges = TraineeBadge.objects.filter(trainee=trainee).select_related('badge')
    
    # Generated certificates
    certificates = Certificate.objects.filter(trainee=trainee)
    
    # Points log
    from apps.gamification.models import ActivityPointsLog
    points_log = ActivityPointsLog.objects.filter(trainee=trainee).order_by('-id')
    
    # Group leaderboard (top 5)
    group_leaderboard = group_members[:5]
    
    context = {
        'profile': profile,
        'group_rank': group_rank,
        'global_rank': global_rank,
        'attendances': attendances,
        'evaluations': evaluations,
        'pending_assignments': pending_assignments,
        'completed_submissions': completed_submissions,
        'badges': badges,
        'certificates': certificates,
        'group': profile.group,
        'points_log': points_log,
        'group_leaderboard': group_leaderboard,
        'is_viewing_as_staff': (request.user.role in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR, CustomUser.Role.SUPERVISOR, CustomUser.Role.LECTURER]),
        # Fetch staff notes with author & timestamp
        'staff_notes': list(TraineeNote.objects.filter(trainee=profile).select_related('author').order_by('-created_at')),
        # Fetch targeted and global announcements
        'announcements': InternalMessage.objects.filter(
            Q(group=profile.group) | Q(group__isnull=True)
        ).order_by('-id'),
    }
    return render(request, 'portal/trainee_dashboard.html', context)


@login_required
@require_POST
def mark_notifications_read(request):
    """Marks all unread notifications of the logged-in user as read."""
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return JsonResponse({'success': True})


@login_required
@require_POST
def delete_announcement_post(request, message_id):
    """Deletes an announcement/InternalMessage and redirect back to dashboard."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    msg = get_object_or_404(InternalMessage, id=message_id)
    try:
        msg.delete()
        messages.success(request, "تم حذف الإعلان والتنبيه بنجاح.")
    except Exception as e:
        messages.error(request, f"فشل حذف الإعلان: {str(e)}")
        
    # Check if request referred from create_announcements_view, redirect there instead
    referer = request.META.get('HTTP_REFERER', '')
    if 'announcements/create' in referer:
        return redirect('portal:create_announcements_view')
    return redirect('portal:admin_management_hub')


@login_required
def create_announcements_view(request):
    """Dedicated management page for creating and reviewing administrative announcements."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        raise Http404("غير مصرح بالدخول.")
        
    from apps.notifications.models import InternalMessage
    announcements = InternalMessage.objects.all().order_by('-created_at')
    
    # Query groups for dropdown selector
    groups = Group.objects.all()
    
    context = {
        'announcements': announcements,
        'groups': groups,
    }
    return render(request, 'portal/create_announcements.html', context)


@login_required
def notifications_unread_count_api(request):
    """API for real-time live polling of unread bell notifications."""
    count = request.user.notifications.filter(is_read=False).count()
    return JsonResponse({'unread_count': count})


@login_required
def send_notifications_view(request):
    """Dedicated management page for sending and reviewing individual/group bell notifications."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        raise Http404("غير مصرح بالدخول.")
        
    from apps.notifications.models import Notification
    
    # If request is POST, handle notification sending
    if request.method == 'POST':
        target_type = request.POST.get('target_type')
        title = request.POST.get('title')
        message = request.POST.get('message')
        notif_type = request.POST.get('notification_type', 'system')
        
        users_to_notify = []
        target_desc = ""
        
        try:
            if target_type == 'user':
                user_ids = request.POST.getlist('user_ids')
                if user_ids:
                    users_to_notify = list(CustomUser.objects.filter(id__in=user_ids))
                    if len(users_to_notify) == 1:
                        target_desc = f"المستخدم {users_to_notify[0].get_full_name() or users_to_notify[0].username}"
                    else:
                        target_desc = f"{len(users_to_notify)} مستخدمين محددين"
            elif target_type == 'group':
                group_id = request.POST.get('group_id')
                if group_id:
                    group = get_object_or_404(Group, id=group_id)
                    users_to_notify = list(CustomUser.objects.filter(
                        Q(role=CustomUser.Role.TRAINEE, trainee_profile__group=group) |
                        Q(id=group.instructor_id) |
                        Q(id=group.supervisor_id)
                    ).distinct())
                    target_desc = f"منتسبي شعبة {group.name}"
            elif target_type == 'all_trainees':
                users_to_notify = list(CustomUser.objects.filter(role=CustomUser.Role.TRAINEE))
                target_desc = "جميع الطلاب"
            elif target_type == 'all_lecturers':
                users_to_notify = list(CustomUser.objects.filter(role=CustomUser.Role.LECTURER))
                target_desc = "جميع المدربين"
            elif target_type == 'all_supervisors':
                users_to_notify = list(CustomUser.objects.filter(role=CustomUser.Role.SUPERVISOR))
                target_desc = "جميع المشرفين"
            elif target_type == 'all_users':
                users_to_notify = list(CustomUser.objects.all())
                target_desc = "جميع المستخدمين"
                
            if users_to_notify and title and message:
                for u in users_to_notify:
                    Notification.objects.create(
                        user=u,
                        title=title.strip(),
                        message=message.strip(),
                        notification_type=notif_type
                    )
                    if notif_type in [Notification.Type.EMAIL, Notification.Type.BOTH] and u.email:
                        try:
                            from django.core.mail import send_mail
                            send_mail(
                                subject=f"تنبيه من مبادرة 1000 مبرمج: {title.strip()}",
                                message=message.strip(),
                                from_email=None,
                                recipient_list=[u.email],
                                fail_silently=True
                            )
                        except Exception:
                            pass
                messages.success(request, f"تم إرسال الإشعار لـ ({target_desc}) بنجاح!")
            else:
                messages.warning(request, "يرجى تعبئة جميع الحقول المستهدفة وإدخال البيانات.")
        except Exception as e:
            messages.error(request, f"فشل إرسال الإشعار: {str(e)}")
            
        return redirect('portal:send_notifications_view')

    # Query all sent notifications (limit to last 30 for performance)
    sent_notifications = Notification.objects.all().select_related('user').order_by('-created_at')[:30]
    
    # Query all users (lecturers & trainees) for individual select
    all_users = CustomUser.objects.filter(role__in=[CustomUser.Role.TRAINEE, CustomUser.Role.LECTURER]).order_by('role', 'username')
    
    # Query groups
    groups = Group.objects.all()
    
    context = {
        'sent_notifications': sent_notifications,
        'all_users': all_users,
        'groups': groups,
    }
    return render(request, 'portal/send_notifications.html', context)


@login_required
@require_POST
def delete_notification_post(request, notification_id):
    """Deletes a specific notification."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    from apps.notifications.models import Notification
    notif = get_object_or_404(Notification, id=notification_id)
    try:
        notif.delete()
        messages.success(request, "تم حذف الإشعار بنجاح.")
    except Exception as e:
        messages.error(request, f"فشل حذف الإشعار: {str(e)}")
        
    return redirect('portal:send_notifications_view')


# ==========================================
# Administrative Edit, Delete, Import & Account Generation Views
# ==========================================

@login_required
@require_POST
def edit_lecturer_post(request, lecturer_id):
    """Updates an existing lecturer's details and profile."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    user = get_object_or_404(CustomUser, id=lecturer_id, role=CustomUser.Role.LECTURER)
    first_name = request.POST.get('first_name')
    last_name = request.POST.get('last_name')
    email = request.POST.get('email')
    specialty = request.POST.get('specialty')
    bio = request.POST.get('bio')
    
    try:
        from django.db import transaction
        with transaction.atomic():
            if first_name: user.first_name = first_name.strip()
            if last_name: user.last_name = last_name.strip()
            if email: user.email = email.strip()
            user.save()
            
            profile, _ = LecturerProfile.objects.get_or_create(user=user)
            if specialty: profile.specialty = specialty.strip()
            if bio is not None: profile.bio = bio.strip()
            profile.save()
            
            messages.success(request, f"تم تحديث بيانات المحاضر {user.get_full_name() or user.username} بنجاح.")
    except Exception as e:
        messages.error(request, f"فشل التعديل: {str(e)}")
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def delete_lecturer_post(request, lecturer_id):
    """Deletes a lecturer user account and profile."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    user = get_object_or_404(CustomUser, id=lecturer_id, role=CustomUser.Role.LECTURER)
    try:
        user.delete()
        messages.success(request, "تم حذف حساب المحاضر بنجاح.")
    except Exception as e:
        messages.error(request, f"فشل الحذف: {str(e)}")
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def edit_trainee_post(request, trainee_id):
    """Updates an existing trainee's details and profile."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    profile = get_object_or_404(TraineeProfile, id=trainee_id)
    user = profile.user
    first_name = request.POST.get('first_name')
    last_name = request.POST.get('last_name')
    email = request.POST.get('email')
    group_id = request.POST.get('group')
    gov = request.POST.get('governorate')
    dist = request.POST.get('district')
    uni = request.POST.get('university')
    col = request.POST.get('college')
    dept = request.POST.get('department')
    stage = request.POST.get('academic_stage')
    spec = request.POST.get('specialty')
    
    try:
        from django.db import transaction
        with transaction.atomic():
            if first_name: user.first_name = first_name.strip()
            if last_name: user.last_name = last_name.strip()
            if email: user.email = email.strip()
            user.save()
            
            group = Group.objects.get(id=group_id) if group_id else None
            profile.group = group
            if gov: profile.governorate = gov.strip()
            if dist is not None: profile.district = dist.strip()
            if uni is not None: profile.university = uni.strip()
            if col is not None: profile.college = col.strip()
            if dept is not None: profile.department = dept.strip()
            if stage is not None: profile.academic_stage = stage.strip()
            if spec is not None: profile.specialty = spec.strip()
            profile.save()
            
            messages.success(request, f"تم تحديث بيانات المتدرب {user.get_full_name() or user.username} بنجاح.")
    except Exception as e:
        messages.error(request, f"فشل التعديل: {str(e)}")
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def delete_trainee_post(request, trainee_id):
    """Deletes a trainee user account and profile."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    profile = get_object_or_404(TraineeProfile, id=trainee_id)
    try:
        profile.user.delete()
        messages.success(request, "تم حذف حساب المتدرب بنجاح.")
    except Exception as e:
        messages.error(request, f"فشل الحذف: {str(e)}")
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def save_trainee_notes_post(request, trainee_id):
    """Allows superadmins, directors, supervisors, and lecturers to save profile notes for a trainee."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR, CustomUser.Role.SUPERVISOR, CustomUser.Role.LECTURER]:
        messages.error(request, "غير مصرح لك بإضافة ملاحظات.")
        return redirect('portal:admin_management_hub')
        
    profile = get_object_or_404(TraineeProfile, id=trainee_id)
    notes = request.POST.get('notes', '')
    if notes.strip():
        try:
            from apps.users.models import TraineeNote
            TraineeNote.objects.create(
                trainee=profile,
                author=request.user,
                note=notes.strip()
            )
            profile.notes = notes.strip()
            profile.save()
            messages.success(request, "تم حفظ الملاحظة والتوجيه بنجاح مع وثائق كاتب الملاحظة ووقت إضافتها.")
        except Exception as e:
            messages.error(request, f"فشل حفظ الملاحظة: {str(e)}")
    else:
        messages.warning(request, "يرجى كتابة نص الملاحظة قبل الحفظ.")
        
    return redirect('portal:view_trainee_profile_detail', trainee_user_id=profile.user.id)


@login_required
@require_POST
def edit_group_post(request, group_id):
    """Updates an existing group's details."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    group = get_object_or_404(Group, id=group_id)
    name = request.POST.get('name')
    course_id = request.POST.get('course')
    course_title = request.POST.get('course_title', '').strip()
    instructor_id = request.POST.get('instructor')
    supervisor_id = request.POST.get('supervisor')
    classroom = request.POST.get('classroom')
    code = request.POST.get('code')
    days_list = request.POST.getlist('days')
    days = "، ".join(days_list) if days_list else request.POST.get('days', '')
    start_time = request.POST.get('start_time')
    end_time = request.POST.get('end_time')
    
    try:
        # Resolve course/subject dynamically
        course = None
        if course_title:
            course, _ = Course.objects.get_or_create(
                title=course_title,
                defaults={'hours': 60, 'description': f"مادة {course_title}"}
            )
        elif course_id:
            course = Course.objects.get(id=course_id)

        from django.db import transaction
        with transaction.atomic():
            if name: group.name = name.strip()
            if course: group.course = course
            group.instructor = CustomUser.objects.get(id=instructor_id) if instructor_id else None
            group.supervisor = CustomUser.objects.get(id=supervisor_id) if supervisor_id else None
            if classroom: group.classroom = classroom.strip()
            if code: group.code = code.strip()
            if days: group.days = days.strip()
            if start_time: group.start_time = start_time
            if end_time: group.end_time = end_time
            group.save()
            
            messages.success(request, f"تم تحديث بيانات الشعبة/المجموعة '{group.name}' بنجاح.")
    except Exception as e:
        messages.error(request, f"فشل التعديل: {str(e)}")
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def delete_group_post(request, group_id):
    """Deletes an existing group."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    group = get_object_or_404(Group, id=group_id)
    try:
        group.delete()
        messages.success(request, "تم حذف الشعبة/المجموعة بنجاح.")
    except Exception as e:
        messages.error(request, f"فشل الحذف: {str(e)}")
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def edit_lecture_post(request, lecture_id):
    """Updates an existing lecture's details."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    lecture = get_object_or_404(Lecture, id=lecture_id)
    title = request.POST.get('title')
    group_id = request.POST.get('group')
    date_val = request.POST.get('date')
    start_time = request.POST.get('start_time')
    end_time = request.POST.get('end_time')
    
    try:
        from django.db import transaction
        with transaction.atomic():
            if title: lecture.title = title.strip()
            if group_id: lecture.group = Group.objects.get(id=group_id)
            if date_val: lecture.date = date_val
            if start_time: lecture.start_time = start_time
            if end_time: lecture.end_time = end_time
            lecture.save()
            
            messages.success(request, f"تم تحديث بيانات المحاضرة '{lecture.title}' بنجاح.")
    except Exception as e:
        messages.error(request, f"فشل التعديل: {str(e)}")
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def delete_lecture_post(request, lecture_id):
    """Deletes an existing lecture."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    lecture = get_object_or_404(Lecture, id=lecture_id)
    try:
        lecture.delete()
        messages.success(request, "تم حذف المحاضرة بنجاح.")
    except Exception as e:
        messages.error(request, f"فشل الحذف: {str(e)}")
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def import_lecturers_view(request):
    """Handles Excel file uploads for lecturer bulk importing."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    if request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        try:
            imported, errors = ImportExportService.import_lecturers_from_excel(excel_file)
            if imported > 0:
                messages.success(request, f"تم استيراد {imported} مدرب/محاضر بنجاح!")
            if errors:
                for error in errors:
                    messages.warning(request, error)
        except Exception as e:
            messages.error(request, f"فشل في قراءة ملف الإكسل: {str(e)}")
            
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def generate_single_account_post(request):
    """Auto-generates a single user account and returns credentials via JSON."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    username = request.POST.get('username')
    first_name = request.POST.get('first_name', '')
    last_name = request.POST.get('last_name', '')
    role = request.POST.get('role', 'trainee')
    group_id = request.POST.get('group')
    
    if not username:
        return JsonResponse({'success': False, 'message': 'اسم المستخدم مطلوب.'}, status=400)
        
    username = username.strip()
    if CustomUser.objects.filter(username=username).exists():
        return JsonResponse({'success': False, 'message': 'اسم المستخدم هذا مسجل بالفعل.'}, status=400)
        
    import random
    import string
    chars = string.ascii_letters + string.digits
    password = "".join(random.choice(chars) for _ in range(8))
    
    try:
        from django.db import transaction
        with transaction.atomic():
            user = CustomUser.objects.create_user(
                username=username,
                email=f"{username}@1000programmers.org",
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                role=role,
                password=password
            )
            
            group_name = ""
            if role == CustomUser.Role.TRAINEE:
                group = Group.objects.get(id=group_id) if group_id else None
                profile = TraineeProfile.objects.create(
                    user=user,
                    governorate='البصرة',
                    group=group
                )
                user.email = f"{profile.training_number.lower()}@1000programmers.org"
                user.save()
                group_name = group.name if group else ""
            elif role == CustomUser.Role.LECTURER:
                LecturerProfile.objects.create(
                    user=user,
                    specialty='مدرب تقني'
                )
            elif role == CustomUser.Role.SUPERVISOR:
                SupervisorProfile.objects.create(
                    user=user
                )
                
            return JsonResponse({
                'success': True,
                'username': user.username,
                'email': user.email,
                'password': password,
                'role': dict(CustomUser.Role.choices).get(role, role),
                'group': group_name
            })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f"فشل التوليد: {str(e)}"}, status=500)


@login_required
def generate_batch_accounts_view(request):
    """Generates batch accounts and exports them to an Excel spreadsheet."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        raise Http404("غير مصرح.")
        
    if request.method == 'POST':
        prefix = request.POST.get('prefix', 'student')
        count_val = request.POST.get('count', '10')
        count = int(count_val) if count_val.isdigit() else 10
        role = request.POST.get('role', 'trainee')
        group_id = request.POST.get('group_id')
        names_text = request.POST.get('names_list', '')
        
        names_list = [n.strip() for n in names_text.splitlines() if n.strip()] if names_text else None

        try:
            buffer, generated = ImportExportService.generate_batch_accounts(
                prefix=prefix.strip(),
                count=count,
                role=role,
                group_id=group_id,
                names_list=names_list
            )
            
            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="generated_accounts_{prefix}.xlsx"'
            return response
        except Exception as e:
            messages.error(request, f"فشل توليد الحسابات الجماعية: {str(e)}")
            
    return redirect('portal:admin_management_hub')


@login_required
def get_group_students_api(request, group_id):
    """API endpoint to fetch all registered student full names in a specific group."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR, CustomUser.Role.LECTURER, CustomUser.Role.SUPERVISOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    try:
        group = Group.objects.get(id=group_id)
        trainees = TraineeProfile.objects.filter(group=group).select_related('user').order_by('id')
        
        students = []
        names_text_lines = []
        for t in trainees:
            full_name = t.user.get_full_name().strip() or t.user.username
            students.append({
                'id': t.id,
                'user_id': t.user.id,
                'full_name': full_name,
                'username': t.user.username,
                'email': t.user.email
            })
            names_text_lines.append(full_name)
            
        return JsonResponse({
            'success': True,
            'group_id': group.id,
            'group_name': group.name,
            'count': len(students),
            'students': students,
            'names_text': "\n".join(names_text_lines)
        })
    except Group.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'المجموعة غير موجودة.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
def export_lecturers_view(request):
    """Generates and downloads a lecturers spreadsheet."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        raise Http404("غير مصرح.")
        
    buffer = ImportExportService.export_lecturers_to_excel()
    
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="lecturers_report.xlsx"'
    return response


@login_required
@require_POST
def bulk_delete_trainees_post(request):
    """Handles bulk deletion of trainees - selected or all."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    delete_all = request.POST.get('delete_all') == 'true'
    selected_ids = request.POST.getlist('selected_ids')
    
    try:
        if delete_all:
            count = ImportExportService.bulk_delete_trainees(delete_all=True)
            messages.success(request, f"تم حذف جميع المتدربين بنجاح! ({count} متدرب)")
        elif selected_ids:
            ids = [int(x) for x in selected_ids if x.isdigit()]
            count = ImportExportService.bulk_delete_trainees(trainee_ids=ids)
            messages.success(request, f"تم حذف {count} متدرب من المحددين بنجاح!")
        else:
            messages.warning(request, "لم يتم تحديد أي متدرب للحذف.")
    except Exception as e:
        messages.error(request, f"فشل عملية الحذف الجماعي: {str(e)}")
    
    return redirect('portal:admin_management_hub')


@login_required
@require_POST
def bulk_delete_lecturers_post(request):
    """Handles bulk deletion of lecturers - selected or all."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    delete_all = request.POST.get('delete_all') == 'true'
    selected_ids = request.POST.getlist('selected_ids')
    
    try:
        if delete_all:
            count = ImportExportService.bulk_delete_lecturers(delete_all=True)
            messages.success(request, f"تم حذف جميع المدربين بنجاح! ({count} مدرب)")
        elif selected_ids:
            ids = [int(x) for x in selected_ids if x.isdigit()]
            count = ImportExportService.bulk_delete_lecturers(lecturer_ids=ids)
            messages.success(request, f"تم حذف {count} مدرب من المحددين بنجاح!")
        else:
            messages.warning(request, "لم يتم تحديد أي مدرب للحذف.")
    except Exception as e:
        messages.error(request, f"فشل عملية الحذف الجماعي: {str(e)}")
    
    return redirect('portal:admin_management_hub')


# ==========================================
# Daily Reports Views
# ==========================================

@login_required
def submit_daily_report_view(request):
    """Allows instructors to submit a daily academic & attendance report."""
    if request.user.role not in [CustomUser.Role.LECTURER, CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        raise Http404("غير مصرح بالدخول.")

    if request.method == 'POST':
        group_id = request.POST.get('group_id')
        lecture_id = request.POST.get('lecture_id')
        topics_covered = request.POST.get('topics_covered')
        attendance_summary = request.POST.get('attendance_summary')
        outstanding_students = request.POST.get('outstanding_students')
        struggling_students = request.POST.get('struggling_students')
        challenges_and_notes = request.POST.get('challenges_and_notes')
        
        if not group_id or not topics_covered:
            messages.error(request, "الشعبة والمواضيع المشروحة حقول مطلوبة للتقرير اليومي.")
            return redirect('portal:lecturer_dashboard')
            
        group = get_object_or_404(Group, id=group_id)
        lecture = Lecture.objects.filter(id=lecture_id).first() if lecture_id else None
        
        from apps.courses.models import DailyReport
        report = DailyReport.objects.create(
            instructor=request.user,
            group=group,
            lecture=lecture,
            report_date=timezone.now().date(),
            topics_covered=topics_covered.strip(),
            attendance_summary=attendance_summary.strip() if attendance_summary else '',
            outstanding_students=outstanding_students.strip() if outstanding_students else '',
            struggling_students=struggling_students.strip() if struggling_students else '',
            challenges_and_notes=challenges_and_notes.strip() if challenges_and_notes else ''
        )
        
        # Send notification to admins & supervisor
        recipients = CustomUser.objects.filter(role__in=[CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR])
        if group.supervisor:
            recipients = recipients | CustomUser.objects.filter(id=group.supervisor.id)
            
        for rec in recipients.distinct():
            Notification.objects.create(
                user=rec,
                title=f"تقرير يومي جديد من المدرب {request.user.get_full_name() or request.user.username}",
                message=f"تم رفع التقرير اليومي لشعبة '{group.name}' بتاريخ {report.report_date}"
            )
            
        messages.success(request, f"تم رفع التقرير اليومي لشعبة '{group.name}' بنجاح وإرساله للإدارة والمشرفين!")
        return redirect('portal:lecturer_dashboard')
        
    return redirect('portal:lecturer_dashboard')


@login_required
def daily_reports_list_view(request):
    """View daily reports list for SuperAdmins, Directors, Supervisors, and Lecturers."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR, CustomUser.Role.SUPERVISOR, CustomUser.Role.LECTURER]:
        raise Http404("غير مصرح بالدخول.")
        
    from apps.courses.models import DailyReport
    if request.user.role in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        reports = DailyReport.objects.select_related('instructor', 'group', 'lecture', 'reviewed_by').all()
    elif request.user.role == CustomUser.Role.SUPERVISOR:
        reports = DailyReport.objects.select_related('instructor', 'group', 'lecture', 'reviewed_by').filter(
            Q(group__supervisor=request.user) | Q(instructor=request.user)
        )
    else:
        reports = DailyReport.objects.select_related('instructor', 'group', 'lecture', 'reviewed_by').filter(
            instructor=request.user
        )
        
    context = {
        'reports': reports,
    }
    return render(request, 'portal/daily_reports_list.html', context)


@login_required
@require_POST
def review_daily_report_post(request, report_id=None):
    """Allows Admin/Supervisor to add feedback and change status on a Daily Report."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR, CustomUser.Role.SUPERVISOR]:
        return JsonResponse({'success': False, 'message': 'غير مصرح.'}, status=403)
        
    target_report_id = report_id or request.POST.get('report_id')
    if not target_report_id:
        messages.error(request, "لم يتم تحديد التقرير المراد مراجعته.")
        return redirect('portal:daily_reports_list')
        
    from apps.courses.models import DailyReport
    report = get_object_or_404(DailyReport, id=target_report_id)
    status = request.POST.get('status', 'reviewed')
    admin_feedback = request.POST.get('admin_feedback', '')
    
    report.status = status
    if admin_feedback:
        report.admin_feedback = admin_feedback.strip()
    report.reviewed_by = request.user
    report.save()
    
    # Notify instructor
    Notification.objects.create(
        user=report.instructor,
        title=f"تم مراجعة تقريرك اليومي لشعبة {report.group.name}",
        message=f"قام {request.user.get_full_name() or request.user.username} بمراجعة التقرير اليومي وإضافة ملاحظات إدارية عليه."
    )
    
    messages.success(request, f"تم مراجعة وتحديث حالة التقرير اليومي بنجاح.")
    return redirect('portal:daily_reports_list')


# ==========================================
# Profile Edit View (Avatar Upload & Password Change)
# ==========================================

@login_required
def edit_profile_view(request):
    """Allows all users (trainees, lecturers, supervisors, admins) to edit profile avatar, info, and change password."""
    user = request.user
    trainee_profile = getattr(user, 'trainee_profile', None)
    lecturer_profile = getattr(user, 'lecturer_profile', None)
    
    if request.method == 'POST':
        action = request.POST.get('action', 'update_info')
        
        if action == 'change_password':
            old_password = request.POST.get('old_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            if not user.check_password(old_password):
                messages.error(request, "كلمة المرور الحالية غير صحيحة.")
            elif not new_password or len(new_password) < 6:
                messages.error(request, "يجب أن تتكون كلمة المرور الجديدة من 6 أحرف على الأقل.")
            elif new_password != confirm_password:
                messages.error(request, "كلمة المرور الجديدة وتأكيدها غير متطابقين.")
            else:
                user.set_password(new_password)
                user.save()
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, user)
                messages.success(request, "تم تغيير كلمة المرور بنجاح!")
            return redirect('portal:edit_profile')

        else:
            # update profile info and avatar
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            email = request.POST.get('email')
            phone_number = request.POST.get('phone_number')
            
            if first_name is not None: user.first_name = first_name.strip()
            if last_name is not None: user.last_name = last_name.strip()
            if email is not None: user.email = email.strip()
            if phone_number is not None: user.phone_number = phone_number.strip()
            
            if request.FILES.get('avatar'):
                user.avatar = request.FILES['avatar']
                
            user.save()
            
            # Role specific profile update
            if user.role == CustomUser.Role.TRAINEE and trainee_profile:
                uni = request.POST.get('university')
                col = request.POST.get('college')
                dept = request.POST.get('department')
                stage = request.POST.get('academic_stage')
                spec = request.POST.get('specialty')
                gov = request.POST.get('governorate')
                dist = request.POST.get('district')
                
                if uni is not None: trainee_profile.university = uni.strip()
                if col is not None: trainee_profile.college = col.strip()
                if dept is not None: trainee_profile.department = dept.strip()
                if stage is not None: trainee_profile.academic_stage = stage.strip()
                if spec is not None: trainee_profile.specialty = spec.strip()
                if gov is not None: trainee_profile.governorate = gov.strip()
                if dist is not None: trainee_profile.district = dist.strip()
                trainee_profile.save()

            elif user.role == CustomUser.Role.LECTURER and lecturer_profile:
                spec = request.POST.get('specialty')
                bio = request.POST.get('bio')
                if spec is not None: lecturer_profile.specialty = spec.strip()
                if bio is not None: lecturer_profile.bio = bio.strip()
                lecturer_profile.save()

            messages.success(request, "تم تحديث بيانات الملف الشخصي والصورة الشخصية بنجاح!")
            return redirect('portal:edit_profile')

    context = {
        'user': user,
        'trainee_profile': trainee_profile,
        'lecturer_profile': lecturer_profile,
    }
    return render(request, 'portal/edit_profile.html', context)


# ==========================================
# Communication Platform (Chat Hub & Messaging)
# ==========================================

@login_required
def chat_view(request):
    """Main Communication Platform / Real-time Messaging Hub view."""
    user = request.user
    from apps.courses.models import Course
    
    # 1. Fetch available channels (General initiative channel, Course chats, Group chats)
    channels = []
    # General initiative channel
    channels.append({
        'id': 'general',
        'type': 'group',
        'group_id': None,
        'name': 'القناة العامة لمبادرة 1000 مبرمج',
        'icon': 'fa-globe-asia text-warning',
        'category': 'عامة',
        'subtitle': 'مناقشات وتوجيهات عامة لجميع أعضاء المبادرة',
    })
    
    # Course-specific channels (كروبات وتواصل خاص لكل مادة دراسية)
    from apps.courses.models import Course
    courses_qs = Course.objects.all()
    for c in courses_qs:
        channels.append({
            'id': f"course_{c.id}",
            'type': 'course',
            'course_id': c.id,
            'name': f"كروب مادة: {c.title}",
            'icon': 'fa-book-open text-primary',
            'category': 'مواد دراسية',
            'subtitle': f"مجتمع ومناقشات مادة {c.title}",
        })

    # Group-specific channels (كروبات الشعب الدراسية)
    all_groups = list(Group.objects.all())
    if not all_groups:
        c_default = Course.objects.first()
        if not c_default:
            c_default = Course.objects.create(title="أساسيات البرمجة", description="منهج المبادرة العام")
        
        g1 = Group.objects.create(name="الشعبة A", code="GRP-A", course=c_default, classroom="قاعة 1", days="الأحد، الثلاثاء", start_time="16:00", end_time="18:00")
        g2 = Group.objects.create(name="الشعبة B", code="GRP-B", course=c_default, classroom="قاعة 2", days="الاثنين، الأربعاء", start_time="16:00", end_time="18:00")
        all_groups = [g1, g2]

    if user.role == CustomUser.Role.TRAINEE:
        trainee_prof = getattr(user, 'trainee_profile', None)
        user_group = trainee_prof.group if trainee_prof else None
        
        if user_group and user_group in all_groups:
            ordered_groups = [user_group] + [g for g in all_groups if g.id != user_group.id]
        else:
            ordered_groups = all_groups
            
        for g in ordered_groups:
            is_my_group = (user_group and g.id == user_group.id)
            channels.append({
                'id': f"group_{g.id}",
                'type': 'group',
                'group_id': g.id,
                'name': f"كروب شعبة: {g.name}",
                'icon': 'fa-users text-info' if not is_my_group else 'fa-users text-success',
                'category': 'شعب دراسية',
                'subtitle': f"قناة شعبتك الخاصة ({g.name})" if is_my_group else f"قناة وتواصل شعبة {g.name}",
            })
    else: # Lecturers / Admins / Supervisors
        for g in all_groups:
            channels.append({
                'id': f"group_{g.id}",
                'type': 'group',
                'group_id': g.id,
                'name': f"كروب شعبة: {g.name}",
                'icon': 'fa-users text-info',
                'category': 'شعب دراسية',
                'subtitle': f"قناة وتواصل شعبة {g.name}",
            })
            
    # 2. Fetch direct message contacts (Users)
    if user.role == CustomUser.Role.TRAINEE:
        trainee_prof = getattr(user, 'trainee_profile', None)
        if trainee_prof and trainee_prof.group:
            group_members = CustomUser.objects.filter(
                Q(trainee_profile__group=trainee_prof.group) |
                Q(id=trainee_prof.group.instructor_id) |
                Q(role__in=[CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR, CustomUser.Role.SUPERVISOR])
            ).exclude(id=user.id).distinct()
        else:
            group_members = CustomUser.objects.filter(
                role__in=[CustomUser.Role.LECTURER, CustomUser.Role.SUPERVISOR, CustomUser.Role.SUPER_ADMIN]
            ).exclude(id=user.id).distinct()
    else:
        group_members = CustomUser.objects.exclude(id=user.id).order_by('first_name', 'username')[:100]

    contacts = []
    for c_user in group_members:
        unread_count = InternalMessage.objects.filter(sender=c_user, recipient=user, is_read=False).count()
        contacts.append({
            'user_id': c_user.id,
            'name': c_user.get_full_name() or c_user.username,
            'role_display': c_user.get_role_display(),
            'avatar_url': c_user.avatar.url if c_user.avatar else None,
            'unread_count': unread_count,
        })
        
    context = {
        'channels': channels,
        'contacts': contacts,
    }
    return render(request, 'portal/chat.html', context)


@login_required
def chat_fetch_messages_api(request):
    """AJAX endpoint to fetch chat message stream for active target."""
    target_type = request.GET.get('target_type') # 'group', 'course', or 'direct'
    target_id = str(request.GET.get('target_id', ''))
    user = request.user
    
    if target_type == 'course' or target_id.startswith('course_'):
        c_id = int(target_id.replace('course_', ''))
        messages_qs = InternalMessage.objects.filter(course_id=c_id).select_related('sender')
    elif target_type == 'group':
        if target_id and target_id != 'general' and target_id != 'None':
            g_id = int(target_id.replace('group_', ''))
            messages_qs = InternalMessage.objects.filter(group_id=g_id).select_related('sender')
        else:
            messages_qs = InternalMessage.objects.filter(recipient=None, group=None, course=None).select_related('sender')
    elif target_type == 'direct' and target_id:
        recipient_id = int(target_id)
        messages_qs = InternalMessage.objects.filter(
            (Q(sender=user, recipient_id=recipient_id) | Q(sender_id=recipient_id, recipient=user))
        ).select_related('sender')
        
        InternalMessage.objects.filter(sender_id=recipient_id, recipient=user, is_read=False).update(is_read=True)
    else:
        return JsonResponse({'success': False, 'messages': []})

    messages_qs = messages_qs.order_by('created_at')[:200]
    
    data = []
    for m in messages_qs:
        data.append({
            'id': m.id,
            'sender_id': m.sender_id,
            'sender_name': m.sender.get_full_name() or m.sender.username,
            'sender_role': m.sender.get_role_display(),
            'sender_avatar': m.sender.avatar.url if m.sender.avatar else None,
            'content': m.content or '',
            'image_url': m.image.url if m.image else None,
            'file_url': m.file.url if m.file else None,
            'file_name': m.file.name.split('/')[-1] if m.file else None,
            'created_at': m.created_at.strftime("%H:%M - %Y/%m/%d"),
            'is_me': m.sender_id == user.id,
        })

    return JsonResponse({'success': True, 'messages': data})


@login_required
@require_POST
def chat_send_message_api(request):
    """AJAX endpoint to send text/image/file message."""
    target_type = request.POST.get('target_type')
    target_id = str(request.POST.get('target_id', ''))
    content = request.POST.get('content', '').strip()
    image = request.FILES.get('image')
    file_attachment = request.FILES.get('file')
    user = request.user
    
    if not (content or image or file_attachment):
        return JsonResponse({'success': False, 'message': 'لا يمكن إرسال رسالة فارغة.'}, status=400)
        
    msg_kwargs = {
        'sender': user,
        'content': content,
        'image': image,
        'file': file_attachment,
    }
    
    if target_type == 'course' or target_id.startswith('course_'):
        c_id = int(target_id.replace('course_', ''))
        msg_kwargs['course_id'] = c_id
    elif target_type == 'group':
        if target_id and target_id != 'general' and target_id != 'None':
            g_id = int(target_id.replace('group_', ''))
            msg_kwargs['group_id'] = g_id
        else:
            msg_kwargs['group'] = None
            msg_kwargs['recipient'] = None
            msg_kwargs['course'] = None
    elif target_type == 'direct' and target_id:
        msg_kwargs['recipient_id'] = int(target_id)
    else:
        return JsonResponse({'success': False, 'message': 'وجهة إرسال غير صالحة.'}, status=400)

    message = InternalMessage.objects.create(**msg_kwargs)
    
    return JsonResponse({
        'success': True,
        'message': {
            'id': message.id,
            'sender_id': message.sender_id,
            'sender_name': message.sender.get_full_name() or message.sender.username,
            'sender_avatar': message.sender.avatar.url if message.sender.avatar else None,
            'content': message.content or '',
            'image_url': message.image.url if message.image else None,
            'file_url': message.file.url if message.file else None,
            'file_name': message.file.name.split('/')[-1] if message.file else None,
            'created_at': message.created_at.strftime("%H:%M - %Y/%m/%d"),
            'is_me': True,
        }
    })


@login_required
def chat_unread_count_api(request):
    """API for total unread direct messages for header badge."""
    count = InternalMessage.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'unread_count': count})


@login_required
@require_POST
def chat_delete_message_api(request, message_id):
    """AJAX endpoint to delete a chat message sent by current user or admin."""
    message = get_object_or_404(InternalMessage, id=message_id)
    
    is_admin = request.user.role in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]
    if message.sender_id != request.user.id and not is_admin:
        return JsonResponse({'success': False, 'message': 'غير مصرح بحذف هذه الرسالة.'}, status=403)
        
    message.delete()
    return JsonResponse({'success': True, 'message_id': message_id})


# ==========================================
# Initiative Media & Announcements Center
# ==========================================

def initiative_media_view(request):
    """Public & Student Media Center showcasing videos, photo gallery, and announcements."""
    from apps.portal.models import InitiativeMedia
    user = request.user
    
    media_items = InitiativeMedia.objects.select_related('created_by').all()
    if not user.is_authenticated or user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR, CustomUser.Role.LECTURER, CustomUser.Role.SUPERVISOR]:
        media_items = media_items.filter(is_public=True)

    videos = [m for m in media_items if m.media_type == InitiativeMedia.MediaType.VIDEO]
    images = [m for m in media_items if m.media_type == InitiativeMedia.MediaType.IMAGE]
    announcements = [m for m in media_items if m.media_type == InitiativeMedia.MediaType.ANNOUNCEMENT]
    
    context = {
        'all_media': media_items,
        'videos': videos,
        'images': images,
        'announcements': announcements,
    }
    return render(request, 'portal/initiative_media.html', context)


@login_required
@require_POST
def add_initiative_media_post(request):
    """Allows Admins only to publish initiative photos, videos, and media updates."""
    if request.user.role not in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR]:
        messages.error(request, "غير مصرح بنشر محتوى الميديا. هذه الخاصية مقتصرة على إدارة المبادرة فقط.")
        return redirect('portal:initiative_media_view')
        
    title = request.POST.get('title')
    description = request.POST.get('description', '')
    media_type = request.POST.get('media_type', 'image')
    video_url = request.POST.get('video_url', '')
    is_public = request.POST.get('is_public') == 'on' or request.POST.get('is_public') == 'true'
    
    image = request.FILES.get('image')
    video_file = request.FILES.get('video_file')
    attachment = request.FILES.get('attachment')
    
    if not title:
        messages.error(request, "عنوان المحتوى حقل مطلوب.")
        return redirect('portal:initiative_media_view')
        
    from apps.portal.models import InitiativeMedia
    InitiativeMedia.objects.create(
        title=title.strip(),
        description=description.strip() if description else None,
        media_type=media_type,
        image=image,
        video_file=video_file,
        video_url=video_url.strip() if video_url else None,
        attachment=attachment,
        is_public=is_public,
        created_by=request.user
    )
    
    messages.success(request, "تم نشر المحتوى الإعلامي والفيديو بنجاح وإظهاره للطلاب والجميع!")
    return redirect('portal:initiative_media_view')


@login_required
@require_POST
def delete_initiative_media_post(request, media_id):
    """Allows deletion of initiative media items."""
    from apps.portal.models import InitiativeMedia
    media = get_object_or_404(InitiativeMedia, id=media_id)
    
    if request.user.role in [CustomUser.Role.SUPER_ADMIN, CustomUser.Role.DIRECTOR] or media.created_by == request.user:
        media.delete()
        messages.success(request, "تم حذف عنصر الميديا بنجاح.")
    else:
        messages.error(request, "غير مصرح لك بحذف هذا العنصر.")
        
    return redirect('portal:initiative_media_view')

