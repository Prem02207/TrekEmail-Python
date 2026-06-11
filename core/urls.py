from django.contrib import admin
from django.urls import path
from dashboard.views import (
    dashboard_view,
    SendBulkEmailView,
    DashboardStatsView,
    TrackEmailView
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # 1. Dashboard UI (Root URL)
    path('', dashboard_view, name='dashboard'),

    # 2. Bulk Email API (Matches the fetch URL in your HTML)
    path('send-bulk-email/', SendBulkEmailView.as_view(), name='send-bulk-email'),

    # 3. Stats API
    path('api/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),

    # 4. Tracking Pixel (Matches the .png extension)
    path('track/<str:log_id>.png/', TrackEmailView.as_view(), name='track-email'),
]