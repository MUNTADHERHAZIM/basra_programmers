from django.contrib import admin
from .models import LearningInstruction, SiteConfiguration, ContactMessage

admin.site.register(SiteConfiguration)


@admin.register(LearningInstruction)
class LearningInstructionAdmin(admin.ModelAdmin):
    list_display = ('title', 'audience', 'is_published', 'order', 'created_at')
    list_filter = ('audience', 'is_published')
    search_fields = ('title', 'summary', 'content')
    list_editable = ('is_published', 'order')


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'name', 'category', 'status', 'priority', 'governorate', 'is_read', 'created_at')
    list_filter = ('status', 'category', 'priority', 'is_read', 'governorate', 'created_at')
    search_fields = ('name', 'email', 'phone', 'subject', 'message', 'admin_notes', 'admin_reply')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('status', 'priority', 'is_read')

