"""
GovernorateMiddleware — طبقة العزل التلقائي للبيانات بين المحافظات.

يُحدد هذا الـ Middleware محافظة المستخدم الحالي ويضعها في:
    - request.governorate  → كائن Governorate (أو None للـ super admin)
    - request.is_national  → True إذا كان يرى كل المحافظات

يُمكّن Views من استخدام request.governorate مباشرة دون التحقق في كل مكان.
"""


class GovernorateMiddleware:
    """
    Middleware يُضيف معلومات المحافظة لكل request.
    يعمل بعد AuthenticationMiddleware لضمان وجود المستخدم.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # تحديد محافظة المستخدم الحالي
        self._set_governorate_context(request)
        response = self.get_response(request)
        return response

    def _set_governorate_context(self, request):
        """يُضيف governorate و is_national إلى الـ request"""
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            request.governorate = None
            request.is_national = False
            return

        user = request.user

        # Super Admin → وصول وطني كامل
        if user.role == 'super_admin':
            request.governorate = None
            request.is_national = True
            return

        # باقي المستخدمين → محافظتهم المحددة
        request.governorate = user.governorate
        request.is_national = False
