from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, TraineeProfile, LecturerProfile, SupervisorProfile

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        ('بيانات الدور والصلاحيات', {'fields': ('role', 'phone_number', 'national_id', 'avatar')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('بيانات الدور والصلاحيات', {'fields': ('role', 'phone_number', 'national_id', 'avatar')}),
    )

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(TraineeProfile)
admin.site.register(LecturerProfile)
admin.site.register(SupervisorProfile)
