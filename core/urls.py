from django.contrib import admin
from django.urls import path
# FilteredLogsView ko import mein add kar diya hai
from dashboard.views import dashboard_view, DashboardStatsView, SendBulkEmailView, TrackEmailView, FilteredLogsView

urlpatterns = [
    path('admin/', admin.site.urls),

    # 1. Dashboard UI
    path('', dashboard_view, name='home'),

    # 2. Stats API
    path('api/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),

    # 3. Filtered Logs API (Date wise search ke liye)
    path('api/filtered-logs/', FilteredLogsView.as_view(), name='filtered-logs'),

    # 4. Bulk Email API
    path('send-bulk-email/', SendBulkEmailView.as_view(), name='send-bulk-email'),

    # 5. Tracking
    path('track/<str:log_id>/', TrackEmailView.as_view(), name='track-email'),
]