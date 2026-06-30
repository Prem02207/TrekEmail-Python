import pandas as pd
import base64
import threading
import time
import smtplib
import os
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.db import close_old_connections
from django.db.models import Count
from django.db.models.functions import TruncDate
from datetime import timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .models import EmailLog


# --- 1. Background Task for Email Sending (Brevo Configured) ---
def send_emails_task(recipient_data, subject, body, is_html=True):
    def _run_email_task():
        # Brevo (Sendinblue) settings from Environment Variables
        smtp_server = "smtp-brevo.com"
        smtp_port = 2525
        sender_email = os.environ.get('EMAIL_HOST_USER')
        sender_password = os.environ.get('EMAIL_HOST_PASSWORD')

        if not sender_email or not sender_password:
            print("ERROR: Brevo credentials missing in environment variables!")
            return

        close_old_connections()
        try:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
            server.starttls()
            server.login(sender_email, sender_password)

            for data in recipient_data:
                try:
                    email = data.get('email')
                    if not email: continue

                    # Personalization logic
                    personalized_body = body
                    for key, value in data.items():
                        if key != 'email':
                            personalized_body = personalized_body.replace(f"{{{{{key}}}}}", str(value))

                    log = EmailLog.objects.create(email_address=email, status='Unread', deliverability='Sent')
                    pixel_url = f"https://trekemail-python.onrender.com/track/{log.id}.png"
                    full_body = f"{personalized_body} <img src='{pixel_url}' width='1' height='1' />"

                    msg = MIMEMultipart()
                    msg['From'] = f"Prem Yadav <{sender_email}>"
                    msg['To'] = email
                    msg['Subject'] = subject
                    msg.attach(MIMEText(full_body, 'html' if is_html else 'plain'))

                    server.sendmail(sender_email, email, msg.as_string())
                    time.sleep(0.1)
                except Exception as inner_e:
                    print(f"Error sending to {email}: {inner_e}")

            server.quit()
        except Exception as e:
            print(f"CRITICAL SMTP ERROR: {e}")

    threading.Thread(target=_run_email_task).start()


# --- 2. Dashboard View ---
def dashboard_view(request):
    return render(request, 'dashboard.html')


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
            'status': 'Sent',
            'mark': log.status,
            'deliverability': log.deliverability,
            'date_sent': timezone.localtime(log.created_at).strftime('%Y-%m-%d %H:%M')
        } for log in logs_queryset[:20]]
        return Response({"logs": logs, "stats": stats})


# --- 4. Tracking Pixel ---
class TrackEmailView(APIView):
    def get(self, request, log_id):
        gif_data = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
        try:
            log = EmailLog.objects.get(id=log_id.replace('.png', ''))
            if log.status == 'Unread':
                log.status = 'Read'
                log.save(update_fields=['status'])
        except:
            pass
        response = HttpResponse(gif_data, content_type="image/gif")
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response


# --- 5. Bulk Email Sending ---
class SendBulkEmailView(APIView):
    def post(self, request):
        try:
            csv_file = request.FILES.get('csv_file')
            manual_email = request.POST.get('manual_email')
            subject = request.POST.get('subject')
            body = request.POST.get('body')
            content_format = request.POST.get('format', 'html')

            if csv_file:
                df = pd.read_csv(csv_file)
                recipients = df.to_dict('records')
            else:
                recipients = [{'email': manual_email}]

            send_emails_task(recipients, subject, body, is_html=(content_format == 'html'))
            return JsonResponse({"status": "Success", "message": "Background task initiated."})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# --- 6. Stats API ---
class DashboardStatsView(APIView):
    def get(self, request):
        logs_queryset = EmailLog.objects.all().order_by('-created_at')
        seven_days_ago = timezone.now().date() - timedelta(days=7)

        stats = {
            "total_sent": logs_queryset.count(),
            "inbox_count": logs_queryset.filter(deliverability='Inbox').count(),
            "spam_count": logs_queryset.filter(deliverability='Spam').count(),
            "read_count": logs_queryset.filter(status='Read').count(),
            "unread_count": logs_queryset.filter(status='Unread').count(),
        }

        logs = [{
            'email_address': log.email_address,
            'status': 'Sent',
            'mark': log.status,
            'deliverability': log.deliverability,
            'date_sent': log.created_at.strftime('%Y-%m-%d %H:%M') if log.created_at else 'N/A'
        } for log in logs_queryset[:20]]

        return Response({
            "stats": stats,
            "logs": logs,
            "date_stats": list(EmailLog.objects.filter(created_at__date__gte=seven_days_ago)
                               .values('created_at__date').annotate(date=TruncDate('created_at'), count=Count('id')))
        })