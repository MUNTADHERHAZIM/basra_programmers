from django.urls import path
from . import views

app_name = 'portal'

urlpatterns = [
    path('', views.landing, name='landing'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
    
    # Custom Error Pages Preview Routes
    path('404/', views.custom_404_view, name='custom_404'),
    path('403/', views.custom_403_view, name='custom_403'),
    path('500/', views.custom_500_view, name='custom_500'),

    
    # Dashboard Redirector
    path('dashboard/', views.dashboard_redirect, name='dashboard'),
    
    # Role-based dashboards
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/lecturer/', views.lecturer_dashboard, name='lecturer_dashboard'),
    path('dashboard/supervisor/', views.supervisor_dashboard, name='supervisor_dashboard'),
    path('dashboard/trainee/', views.trainee_dashboard, name='trainee_dashboard'),
    path('manage/governorates/', views.governorates_management_view, name='governorates_management'),
    path('manage/governorate/activate/', views.activate_governorate_post, name='activate_governorate_post'),
    path('manage/branch/add/', views.add_branch_post, name='add_branch_post'),

    
    # Public certificate verification
    path('verify/<str:token>/', views.verify_certificate, name='verify_certificate'),
    path('trainee/<int:trainee_user_id>/profile/', views.view_trainee_profile_detail, name='view_trainee_profile_detail'),
    path('notifications/mark-read/', views.mark_notifications_read, name='mark_notifications_read'),
    path('manage/announcement/<int:message_id>/delete/', views.delete_announcement_post, name='delete_announcement_post'),
    path('manage/announcements/create/', views.create_announcements_view, name='create_announcements_view'),
    path('manage/notifications/send/', views.send_notifications_view, name='send_notifications_view'),
    path('manage/notification/<int:notification_id>/delete/', views.delete_notification_post, name='delete_notification_post'),
    
    # Attendance & QR Codes
    path('lecture/<int:lecture_id>/qr/', views.lecture_qr_view, name='lecture_qr_view'),
    path('lecture/<int:lecture_id>/qr/token/', views.get_lecture_qr_token, name='get_lecture_qr_token'),
    path('scan/', views.scan_qr_page, name='scan_qr_page'),
    path('scan/mark/', views.mark_attendance_post, name='mark_attendance_post'),
    path('lecture/<int:lecture_id>/attendance/manual/', views.mark_attendance_manual_view, name='mark_attendance_manual'),
    
    # Calendar module
    path('calendar/', views.calendar_view, name='calendar_view'),
    
    # Import/Export
    path('trainees/import/', views.import_trainees_view, name='import_trainees_view'),
    path('trainees/export/', views.export_trainees_view, name='export_trainees_view'),
    path('activity-log/', views.activity_log_view, name='activity_log'),
    
    # Management Hub & Creation Forms
    path('manage/hub/', views.admin_management_hub, name='admin_management_hub'),
    path('manage/lecturer/add/', views.add_lecturer_post, name='add_lecturer_post'),
    path('manage/lecturer/<int:lecturer_id>/edit/', views.edit_lecturer_post, name='edit_lecturer_post'),
    path('manage/lecturer/<int:lecturer_id>/delete/', views.delete_lecturer_post, name='delete_lecturer_post'),
    
    path('manage/trainee/add/', views.add_trainee_post, name='add_trainee_post'),
    path('manage/trainee/<int:trainee_id>/edit/', views.edit_trainee_post, name='edit_trainee_post'),
    path('manage/trainee/<int:trainee_id>/delete/', views.delete_trainee_post, name='delete_trainee_post'),
    path('manage/trainee/<int:trainee_id>/notes/', views.save_trainee_notes_post, name='save_trainee_notes_post'),
    
    path('manage/group/add/', views.add_group_post, name='add_group_post'),
    path('manage/group/<int:group_id>/edit/', views.edit_group_post, name='edit_group_post'),
    path('manage/group/<int:group_id>/delete/', views.delete_group_post, name='delete_group_post'),
    
    path('manage/lecture/add/', views.add_lecture_post, name='add_lecture_post'),
    path('manage/lecture/<int:lecture_id>/edit/', views.edit_lecture_post, name='edit_lecture_post'),
    path('manage/lecture/<int:lecture_id>/delete/', views.delete_lecture_post, name='delete_lecture_post'),
    
    # Dedicated Lectures & Course Materials Hub
    path('lectures/', views.lectures_hub_view, name='lectures_hub'),
    path('lectures/upload/', views.upload_lecture_material_post, name='upload_lecture_material'),
    path('lectures/<int:lecture_id>/edit-material/', views.edit_lecture_material_post, name='edit_lecture_material'),
    path('lectures/<int:lecture_id>/delete-material/', views.delete_lecture_material_post, name='delete_lecture_material'),
    
    path('manage/lecturers/import/', views.import_lecturers_view, name='import_lecturers_view'),
    path('manage/lecturers/export/', views.export_lecturers_view, name='export_lecturers_view'),
    path('manage/trainees/bulk-delete/', views.bulk_delete_trainees_post, name='bulk_delete_trainees_post'),
    path('manage/lecturers/bulk-delete/', views.bulk_delete_lecturers_post, name='bulk_delete_lecturers_post'),
    path('manage/accounts/', views.accounts_management_view, name='accounts_management'),
    path('manage/accounts/generate-single/', views.generate_single_account_post, name='generate_single_account_post'),
    path('manage/accounts/generate-batch/', views.generate_batch_accounts_view, name='generate_batch_accounts_view'),
    path('manage/accounts/user/<int:user_id>/reset-password/', views.reset_user_password_post, name='reset_user_password_post'),
    path('manage/accounts/user/<int:user_id>/send-telegram/', views.send_credentials_telegram_post, name='send_credentials_telegram_post'),
    path('manage/accounts/user/<int:user_id>/toggle-active/', views.toggle_user_active_post, name='toggle_user_active_post'),

    path('manage/accounts/bulk-action/', views.bulk_accounts_action_post, name='bulk_accounts_action_post'),
    path('manage/accounts/export-excel/', views.export_accounts_excel_view, name='export_accounts_excel'),



    path('manage/groups/export/', views.export_groups_view, name='export_groups_view'),
    path('manage/groups/import/', views.import_groups_view, name='import_groups_view'),
    path('manage/lectures/export/', views.export_lectures_view, name='export_lectures_view'),
    path('manage/lectures/import/', views.import_lectures_view, name='import_lectures_view'),
    path('manage/course/add/', views.add_course_post, name='add_course_post'),
    path('manage/course/<int:course_id>/edit/', views.edit_course_post, name='edit_course_post'),
    path('manage/course/<int:course_id>/delete/', views.delete_course_post, name='delete_course_post'),
    path('manage/badge/add/', views.add_badge_post, name='add_badge_post'),
    path('manage/badge/award/', views.award_badge_post, name='award_badge_post'),
    path('manage/certificate/generate/', views.generate_certificate_post, name='generate_certificate_post'),
    path('manage/announcement/add/', views.add_announcement_post, name='add_announcement_post'),
    path('manage/settings/update/', views.update_site_config_post, name='update_site_config_post'),
    
    # Assignments, Projects & Grades
    path('group/<int:group_id>/assignment/create/', views.create_assignment_view, name='create_assignment'),
    path('assignment/<int:assignment_id>/submit/', views.submit_assignment_view, name='submit_assignment'),
    path('submission/<int:submission_id>/grade/', views.grade_submission_view, name='grade_submission'),
    path('lecture/<int:lecture_id>/evaluate/students/', views.evaluate_students_view, name='evaluate_students'),
    path('lecture/<int:lecture_id>/evaluate/lecturer/', views.evaluate_lecturer_view, name='evaluate_lecturer'),
    
    # Daily Reports
    path('reports/daily/submit/', views.submit_daily_report_view, name='submit_daily_report'),
    path('reports/daily/list/', views.daily_reports_list_view, name='daily_reports_list'),
    path('reports/daily/review/', views.review_daily_report_post, name='review_daily_report_post_general'),
    path('reports/daily/<int:report_id>/review/', views.review_daily_report_post, name='review_daily_report_post'),
    
    # Communication Platform (Chat Hub)
    path('chat/', views.chat_view, name='chat_view'),
    path('chat/fetch/', views.chat_fetch_messages_api, name='chat_fetch_messages_api'),
    path('chat/send/', views.chat_send_message_api, name='chat_send_message_api'),
    path('chat/unread-count/', views.chat_unread_count_api, name='chat_unread_count_api'),
    path('chat/message/<int:message_id>/delete/', views.chat_delete_message_api, name='chat_delete_message_api'),
    path('notifications/unread-count/', views.notifications_unread_count_api, name='notifications_unread_count_api'),

    path('api/group/<int:group_id>/students/', views.get_group_students_api, name='get_group_students_api'),

    # Initiative Media & Announcements
    path('media/', views.initiative_media_view, name='initiative_media_view'),
    path('manage/media/add/', views.add_initiative_media_post, name='add_initiative_media_post'),
    path('manage/media/<int:media_id>/delete/', views.delete_initiative_media_post, name='delete_initiative_media_post'),

    # Telegram Integration & PWA System
    path('settings/telegram/', views.telegram_settings_view, name='telegram_settings'),
    path('manifest.json', views.pwa_manifest_view, name='pwa_manifest'),
    path('pwa/icon/<int:size>.svg', views.pwa_icon_view, name='pwa_icon'),
    path('sw.js', views.service_worker_view, name='service_worker'),
    path('offline/', views.offline_view, name='offline'),

    # Fallback catch-all 404 page route
    path('<path:invalid_path>/', views.custom_404_view, name='catch_all_404'),
]




