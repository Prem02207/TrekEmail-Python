import pandas as pd
import base64
import requests
import time
import traceback
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
    emails = EmailLog.objects.all().order_by('-created_at')
    context = {
        'recent_emails': emails,
        'total_sent': emails.filter(status__in=['Sent', 'Read']).count(),
        'inbox': emails.filter(deliverability='Inbox').count(),
        'spam': emails.filter(deliverability='Spam').count(),
        'read': emails.filter(status='Read').count(),
        'unread': emails.filter(status='Sent').count(),
    }
    return render(request, 'dashboard.html', context)


# --- Helper Function for Email Sending (API Based) ---
def send_emails_task(recipient_list, subject, body, attach_data, attach_name, attach_type):
    close_old_connections()
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "api-key": settings.BREVO_API_KEY,
        "Content-Type": "application/json"
    }

    for email in recipient_list:
        try:
            log = EmailLog.objects.create(email_address=email, status='Sent', deliverability='Inbox')
            # Tracking pixel URL (log ID ke sath)
            pixel_url = f"https://trekemail-python.onrender.com/track/{log.id}.png/"
            html_content = f"{body} <img src='{pixel_url}' width='1' height='1' />"

            payload = {
                "sender": {"email": "premdemo22@gmail.com", "name": "Prem Demo"},
                "to": [{"email": email}],
                "subject": subject,
                "htmlContent": html_content
            }

            response = requests.post(url, json=payload, headers=headers)
            time.sleep(0.5)

            if response.status_code not in [200, 201]:
                print(f"Brevo API Error for {email}: {response.text}")
        except Exception as e:
            print(f"Error sending to {email}: {e}")


# --- 2. Dashboard Stats API ---
class DashboardStatsView(APIView):
    def get(self, request):
        close_old_connections()
        selected_date = request.query_params.get('date')
        logs = EmailLog.objects.all()

        date_stats = EmailLog.objects.annotate(date=TruncDate('created_at')) \
            .values('date') \
            .annotate(count=Count('id')) \
            .order_by('-date')

        if selected_date and selected_date != 'all':
            logs = logs.filter(created_at__date=selected_date)

        return Response({
            "total_sent": logs.count(),
            "inbox_count": logs.filter(deliverability='Inbox').count(),
            "spam_count": logs.filter(deliverability='Spam').count(),
            "read_count": logs.filter(status='Read').count(),
            "unread_count": logs.filter(status='Sent').count(),
            "date_stats": list(date_stats)
        })


# --- 3. Filtered Logs API ---
class FilteredLogsView(APIView):
    def get(self, request):
        close_old_connections()
        selected_date = request.query_params.get('date')
        logs_queryset = EmailLog.objects.all().order_by('-created_at')

        if selected_date and selected_date != 'all':
            logs_queryset = logs_queryset.filter(created_at__date=selected_date)

        logs = [{
            'email_address': log.email_address,
            'status': log.status,
            'deliverability': log.deliverability,
            'mark': log.status,
            'date_sent': timezone.localtime(log.created_at).strftime('%Y-%m-%d %H:%M')
        } for log in logs_queryset[:20]]

        return Response({"logs": logs})


# --- 4. Bulk Email Sending ---
class SendBulkEmailView(APIView):
    def post(self, request):
        try:
            csv_file = request.FILES.get('csv_file')
            manual_email = request.POST.get('manual_email')
            subject = request.POST.get('subject')
            body = request.POST.get('body')

            recipients = pd.read_csv(csv_file).iloc[:, 0].dropna().tolist() if csv_file else [manual_email]

            send_emails_task(recipients, subject, body, None, None, None)
            return JsonResponse({"status": "Email processed!"})

        except Exception as e:
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)


# --- 5. Tracking Pixel ---
class TrackEmailView(APIView):
    def get(self, request, log_id):
        close_old_connections()
        clean_id = str(log_id).replace('.png', '')
        try:
            log = EmailLog.objects.get(id=clean_id)
            if log.status != 'Read':
                log.status = 'Read'
                log.save()
        except:
            pass

        # Cache-Control headers taaki har bar server par request jaye aur status update ho
        response = HttpResponse(base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"),
                                content_type="image/gif")
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response