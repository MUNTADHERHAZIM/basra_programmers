from django.utils import timezone
from .models import Attendance, LectureQRToken
from apps.courses.models import Lecture
from apps.gamification.services import award_points
import math

def haversine_distance(lat1, lon1, lat2, lon2):
    # Radius of the Earth in km
    R = 6371.0
    
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance_meters = R * c * 1000
    return distance_meters

class AttendanceService:
    @staticmethod
    def generate_qr_token(lecture_id, latitude=None, longitude=None, radius_meters=50.0):
        lecture = Lecture.objects.get(id=lecture_id)
        # Expire older active tokens for this lecture
        LectureQRToken.objects.filter(lecture=lecture, expires_at__gt=timezone.now()).update(expires_at=timezone.now())
        
        token = LectureQRToken.objects.create(
            lecture=lecture,
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters
        )
        return token

    @staticmethod
    def mark_attendance_via_qr(trainee, token_str, trainee_lat=None, trainee_lng=None):
        try:
            qr_token = LectureQRToken.objects.get(token=token_str)
        except LectureQRToken.DoesNotExist:
            return False, "رمز الـ QR غير صالح أو منتهي الصلاحية."

        if qr_token.is_expired:
            return False, "انتهت صلاحية رمز الـ QR المحدد."

        # Check geofencing if token requires it and trainee coordinates are provided
        if qr_token.latitude is not None and qr_token.longitude is not None:
            if trainee_lat is None or trainee_lng is None:
                return False, "يجب تشغيل تحديد الموقع الجغرافي للتحقق من وجودك في القاعة."
            
            distance = haversine_distance(qr_token.latitude, qr_token.longitude, float(trainee_lat), float(trainee_lng))
            if distance > qr_token.radius_meters:
                return False, f"أنت خارج نطاق القاعة التدريبية المسموح به (تبعد {distance:.1f} متر)."

        lecture = qr_token.lecture
        now = timezone.now()
        
        # Calculate delay if student is checking in after lecture start time
        lecture_datetime_start = timezone.make_aware(timezone.datetime.combine(lecture.date, lecture.start_time))
        delay_minutes = 0
        status = Attendance.Status.PRESENT
        
        if now > lecture_datetime_start:
            delay = now - lecture_datetime_start
            delay_minutes = int(delay.total_seconds() / 60)
            if delay_minutes > 15:
                status = Attendance.Status.LATE
        
        attendance, created = Attendance.objects.get_or_create(
            trainee=trainee,
            lecture=lecture,
            defaults={
                'status': status,
                'check_in_time': now,
                'delay_minutes': delay_minutes,
                'method': Attendance.Method.QR
            }
        )
        
        if not created:
            return False, "لقد قمت بتسجيل حضورك لهذه المحاضرة مسبقاً."
            
        # Award points for presence
        if status == Attendance.Status.PRESENT:
            award_points(trainee, 10, f"الحصول على الحضور الملتزم لمحاضرة '{lecture.title}'")
        else:
            award_points(trainee, 5, f"الحضور المتأخر لمحاضرة '{lecture.title}'")

        return True, f"تم تسجيل الحضور بنجاح. الحاضر: {trainee.get_full_name() or trainee.username}، الحالة: {attendance.get_status_display()}"
