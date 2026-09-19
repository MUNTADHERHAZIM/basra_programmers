from django.contrib import admin
from .models import Governorate, Branch


class BranchInline(admin.TabularInline):
    model = Branch
    extra = 1
    fields = ('name', 'code', 'address', 'status', 'contact_person', 'contact_phone')


@admin.register(Governorate)
class GovernorateAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'status', 'active_trainees_count', 'active_groups_count', 'launch_date', 'order')
    list_filter = ('status',)
    search_fields = ('name', 'code')
    list_editable = ('order', 'status')
    inlines = [BranchInline]
    readonly_fields = ('active_trainees_count', 'active_groups_count')

    fieldsets = (
        ('المعلومات الأساسية', {
            'fields': ('name', 'code', 'status', 'launch_date', 'order')
        }),
        ('الوسائط', {
            'fields': ('logo', 'cover_image', 'description'),
        }),
        ('التواصل', {
            'fields': ('contact_email', 'contact_phone'),
        }),
        ('الإحصائيات (للقراءة فقط)', {
            'fields': ('active_trainees_count', 'active_groups_count'),
        }),
    )


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'governorate', 'status', 'contact_person', 'contact_phone')
    list_filter = ('governorate', 'status')
    search_fields = ('name', 'code', 'governorate__name')
