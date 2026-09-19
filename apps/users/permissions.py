"""
نظام صلاحيات المنصة متعددة المحافظات.
يُستخدم في Views للتحقق من صلاحية المستخدم على عمليات معينة.
"""

from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


# ============================================================
# دوال التحقق من الأدوار
# ============================================================

def is_super_admin(user):
    return user.is_authenticated and user.role == 'super_admin'

def is_governorate_admin(user):
    return user.is_authenticated and user.role in ('super_admin', 'governorate_admin')

def is_director_or_above(user):
    return user.is_authenticated and user.role in ('super_admin', 'governorate_admin', 'director')

def is_training_officer_or_above(user):
    return user.is_authenticated and user.role in (
        'super_admin', 'governorate_admin', 'director', 'training_officer'
    )

def is_supervisor_or_above(user):
    return user.is_authenticated and user.role in (
        'super_admin', 'governorate_admin', 'director', 'training_officer', 'supervisor'
    )

def is_lecturer_or_above(user):
    return user.is_authenticated and user.role in (
        'super_admin', 'governorate_admin', 'director',
        'training_officer', 'supervisor', 'lecturer'
    )

def is_staff_member(user):
    """أي كادر (ليس متدرباً ولا زائراً)"""
    return user.is_authenticated and user.role not in ('trainee', 'visitor')

def is_trainee(user):
    return user.is_authenticated and user.role == 'trainee'


# ============================================================
# التحقق من انتماء المستخدم لمحافظة معينة
# ============================================================

def user_belongs_to_governorate(user, governorate):
    """
    يتحقق هل يمكن للمستخدم الوصول لبيانات هذه المحافظة.
    Super Admin → يصل لأي محافظة.
    غيره → يجب أن تكون محافظته = المحافظة المطلوبة.
    """
    if not user.is_authenticated:
        return False
    if user.role == 'super_admin':
        return True
    return user.governorate == governorate


def get_user_governorate_filter(user):
    """
    يُعيد dict الفلترة المناسب حسب دور المستخدم.
    يُستخدم في QuerySets:
        Group.objects.filter(**get_user_governorate_filter(request.user))
    """
    if user.role == 'super_admin':
        return {}  # لا فلترة — يرى الكل
    return {'governorate': user.governorate}


def get_trainees_qs_for_user(user):
    """يُعيد QuerySet المتدربين المناسب لدور المستخدم"""
    from apps.users.models import TraineeProfile
    if user.role == 'super_admin':
        return TraineeProfile.objects.all()
    if user.role in ('governorate_admin', 'director', 'training_officer'):
        return TraineeProfile.objects.filter(user__governorate=user.governorate)
    if user.role == 'supervisor':
        # المشرف يرى مجموعاته فقط
        return TraineeProfile.objects.filter(
            group__supervisor=user,
            user__governorate=user.governorate
        )
    if user.role == 'lecturer':
        # المحاضر يرى مجموعاته فقط
        return TraineeProfile.objects.filter(
            group__instructor=user,
            user__governorate=user.governorate
        )
    return TraineeProfile.objects.none()


def get_groups_qs_for_user(user):
    """يُعيد QuerySet المجموعات المناسب لدور المستخدم"""
    from apps.courses.models import Group
    if user.role == 'super_admin':
        return Group.objects.all()
    if user.role in ('governorate_admin', 'director', 'training_officer'):
        return Group.objects.filter(governorate=user.governorate)
    if user.role == 'supervisor':
        return Group.objects.filter(supervisor=user, governorate=user.governorate)
    if user.role == 'lecturer':
        return Group.objects.filter(instructor=user, governorate=user.governorate)
    return Group.objects.none()


# ============================================================
# Decorators للـ Views
# ============================================================

def require_role(*roles):
    """
    ديكوريتور يتحقق من أن المستخدم يملك أحد الأدوار المحددة.
    مثال:
        @require_role('super_admin', 'governorate_admin')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('portal:login')
            if request.user.role not in roles:
                raise PermissionDenied("ليس لديك صلاحية للوصول لهذه الصفحة")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_governorate_access(view_func):
    """
    ديكوريتور يتحقق من أن المستخدم ينتمي لمحافظة معينة (يُمرر كـ kwarg).
    يُستخدم مع URLs من نوع: /governorate/<gov_id>/...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from apps.locations.models import Governorate
        gov_id = kwargs.get('governorate_id') or kwargs.get('gov_id')
        if gov_id and not request.user.is_super_admin:
            try:
                gov = Governorate.objects.get(pk=gov_id)
            except Governorate.DoesNotExist:
                raise PermissionDenied
            if not user_belongs_to_governorate(request.user, gov):
                raise PermissionDenied("لا تملك صلاحية الوصول لبيانات هذه المحافظة")
        return view_func(request, *args, **kwargs)
    return wrapper
