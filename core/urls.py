from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
# Saare views ko sahi se import karein
from dashboard.views import DashboardStatsView, SendBulkEmailView, TrackEmailView

urlpatterns = [
    path('admin/', admin.site.urls),

    # API endpoints
    path('api/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('api/send-email/', SendBulkEmailView.as_view(), name='send-email'),

    # Tracking endpoint: <str:log_id> use karein taaki .png handle ho sake
    path('track/<str:log_id>/', TrackEmailView.as_view(), name='track-email'),

    # Main Dashboard Page
    path('', TemplateView.as_view(template_name='dashboard.html'), name='home'),
]