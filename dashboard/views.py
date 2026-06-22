import pandas as pd
import base64
import requests
import time
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.db import close_old_connections
from django.db.models import Count
from django.db.models.functions import TruncDate
from .models import EmailLog


# --- 1. Dashboard View ---
def dashboard_view(request):
    return render(request, 'dashboard.html')


# --- 2. Helper Function for Email Sending ---
def send_emails_task(recipient_list, subject, body):
    close_old_connections()
    url = "https://api.brevo.com/v3/smtp/email"

    # Yahan 'settings.BREVO_API_KEY' aapke Render environment variables se aayega
    headers = {"api-key": settings.BREVO_API_KEY, "Content-Type": "application/json"}

    for email in recipient_list:
        try:
            log = EmailLog.objects.create(email_address=email, status='Unread', deliverability='Inbox')
            pixel_url = f"https://trekemail-python.onrender.com/track/{log.id}.png"
            html_content = f"{body} <img src='{pixel_url}' width='1' height='1' />"

            payload = {
                # Yahan sender email update kar diya gaya hai
                "sender": {"email": "info@scriza.in", "name": "Scriza Team"},
                "to": [{"email": email}],
                "subject": subject,
                "htmlContent": html_content
            }
            requests.post(url, json=payload, headers=headers)
            time.sleep(0.2)
        except Exception as e:
            print(f"Error: {e}")


# --- 3. Filtered Logs API ---
class FilteredLogsView(APIView):
    def get(self, request):
        selected_date = request.query_params.get('date')
        if not selected_date:
            return Response({"error": "Date required"}, status=400)

        logs_queryset = EmailLog.objects.filter(created_at__date=selected_date).order_by('-created_at')

        stats = {
            "total_sent": logs_queryset.count(),
            "read_count": logs_queryset.filter(status='Read').count(),
            "unread_count": logs_queryset.filter(status='Unread').count(),
            "inbox_count": logs_queryset.filter(deliverability='Inbox').count(),
            "spam_count": logs_queryset.filter(deliverability='Spam').count(),
        }

        logs = [{
            'email_address': log.email_address,
            'status': log.deliverability,
            'mark': log.status,
            'deliverability': log.deliverability,
            'date_sent': timezone.localtime(log.created_at).strftime('%Y-%m-%d %H:%M')
        } for log in logs_queryset[:20]]

        return Response({"logs": logs, "stats": stats})


# --- 4. Tracking Pixel ---
class TrackEmailView(APIView):
    def get(self, request, log_id):
        gif_data = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        bot_keywords = ['googleimageproxy', 'bingpreview', 'cortex', 'proxy', 'scanner', 'bot', 'spider', 'crawler']
        is_bot = any(bot in user_agent for bot in bot_keywords)

        if not is_bot:
            try:
                log = EmailLog.objects.get(id=log_id.replace('.png', ''))
                if log.status == 'Unread':
                    log.status = 'Read'
                    log.save(update_fields=['status'])
            except EmailLog.DoesNotExist:
                pass

        response = HttpResponse(gif_data, content_type="image/gif")
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


# --- 5. Bulk Email Sending ---
class SendBulkEmailView(APIView):
    def post(self, request):
        try:
            csv_file = request.FILES.get('csv_file')
            manual_email = request.POST.get('manual_email')
            subject = request.POST.get('subject')
            body = request.POST.get('body')
            recipients = pd.read_csv(csv_file).iloc[:, 0].dropna().tolist() if csv_file else [manual_email]
            send_emails_task(recipients, subject, body)
            return JsonResponse({"status": "Success"})
        except Exception:
            return Response({"error": "Failed"}, status=500)


# --- 6. Stats API ---
class DashboardStatsView(APIView):
    def get(self, request):
        logs_queryset = EmailLog.objects.all().order_by('-created_at')
        return Response({
            "stats": {
                "total_sent": logs_queryset.count(),
                "inbox_count": logs_queryset.filter(deliverability='Inbox').count(),
                "spam_count": logs_queryset.filter(deliverability='Spam').count(),
                "read_count": logs_queryset.filter(status='Read').count(),
                "unread_count": logs_queryset.filter(status='Unread').count(),
            },
            "date_stats": list(EmailLog.objects.annotate(date=TruncDate('created_at')).values('date').annotate(
                count=Count('id')).order_by('-date')),
            "logs": [{
                'email_address': log.email_address,
                'status': log.deliverability,
                'mark': log.status,
                'deliverability': log.deliverability,
                'date_sent': timezone.localtime(log.created_at).strftime('%Y-%m-%d %H:%M')
            } for log in logs_queryset[:20]]
        })