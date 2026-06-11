from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from dashboard.views import DashboardStatsView, SendBulkEmailView, TrackEmailView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),

    # URL yahan update kiya (api/ prefix add kiya)
    path('api/send-bulk-email/', SendBulkEmailView.as_view(), name='send-bulk-email'),

    path('track/<str:log_id>/', TrackEmailView.as_view(), name='track-email'),
    path('', TemplateView.as_view(template_name='dashboard.html'), name='home'),
]