from django.contrib import admin
from .models import LearningInstruction, SiteConfiguration

admin.site.register(SiteConfiguration)


@admin.register(LearningInstruction)
class LearningInstructionAdmin(admin.ModelAdmin):
    list_display = ('title', 'audience', 'is_published', 'order', 'created_at')
    list_filter = ('audience', 'is_published')
    search_fields = ('title', 'summary', 'content')
    list_editable = ('is_published', 'order')
