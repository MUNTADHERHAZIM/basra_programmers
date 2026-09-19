from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, TraineeProfile, LecturerProfile, SupervisorProfile

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'first_name', 'last_name', 'role', 'governorate', 'phone_number', 'is_active', 'is_staff']
    list_filter = ['role', 'governorate', 'is_staff', 'is_active', 'gender']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'phone_number', 'national_id']

    fieldsets = UserAdmin.fieldsets + (
        ('بيانات الدور والمحافظة والصلاحيات', {
            'fields': ('role', 'governorate', 'phone_number', 'national_id', 'gender', 'avatar', 'telegram_chat_id', 'temp_password')
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('بيانات الدور والمحافظة والصلاحيات', {
            'fields': ('role', 'governorate', 'first_name', 'last_name', 'email', 'phone_number', 'national_id', 'gender', 'avatar')
        }),
    )

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(TraineeProfile)
admin.site.register(LecturerProfile)
admin.site.register(SupervisorProfile)
