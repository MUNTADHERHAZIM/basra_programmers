from .models import SiteConfiguration


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
    }

    if request.user.is_authenticated:
        unread = request.user.notifications.filter(is_read=False)
        context['unread_notifications_count'] = unread.count()
        context['all_notifications'] = request.user.notifications.all()[:10]

    return context
