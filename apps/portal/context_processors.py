from .models import SiteConfiguration

def site_settings(request):
    config = SiteConfiguration.objects.first()
    if not config:
        # Create a default configuration if it does not exist
        config = SiteConfiguration.objects.create()
        
    context = {
        'site_config': config,
        'unread_notifications_count': 0,
        'all_notifications': []
    }
    
    if request.user.is_authenticated:
        # Fetch unread notifications and total notifications
        unread = request.user.notifications.filter(is_read=False)
        context['unread_notifications_count'] = unread.count()
        context['all_notifications'] = request.user.notifications.all()[:10]
        
    return context
