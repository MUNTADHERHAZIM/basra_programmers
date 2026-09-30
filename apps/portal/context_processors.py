from .models import SiteConfiguration, ContactMessage


def site_settings(request):
    """
    Context processor يُضيف إعدادات الموقع ومعلومات المحافظة لكل Template.
    يُعطي الأولوية للإعداد الخاص بمحافظة المستخدم إن وُجد،
    ويرجع للإعداد الوطني الافتراضي إن لم يوجد.
    """
    # تحديد المحافظة الحالية (من الـ Middleware)
    current_governorate = getattr(request, 'governorate', None)

    # محاولة إيجاد إعداد خاص بالمحافظة أولاً
    config = None
    if current_governorate:
        config = SiteConfiguration.objects.filter(governorate=current_governorate).first()

    # الرجوع للإعداد الوطني (governorate=NULL)
    if not config:
        config = SiteConfiguration.objects.filter(governorate__isnull=True).first()

    # إنشاء إعداد افتراضي إن لم يوجد أي إعداد
    if not config:
        config = SiteConfiguration.objects.create()

    context = {
        'site_config': config,
        'current_governorate': current_governorate,
        'is_national': getattr(request, 'is_national', False),
        'unread_notifications_count': 0,
        'all_notifications': [],
        'unread_support_count': 0,
    }

    if request.user.is_authenticated:
        unread = request.user.notifications.filter(is_read=False)
        context['unread_notifications_count'] = unread.count()
        context['all_notifications'] = request.user.notifications.all()[:10]

        # Calculate unread support inquiries for admins
        if request.user.role in ['super_admin', 'governorate_admin', 'director', 'training_officer']:
            support_qs = ContactMessage.objects.filter(status='new')
            if request.user.role != 'super_admin' and getattr(request.user, 'governorate', None):
                support_qs = support_qs.filter(governorate=request.user.governorate)
            context['unread_support_count'] = support_qs.count()

    return context

