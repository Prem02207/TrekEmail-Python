import pandas as pd
import base64
import requests
import time
import smtplib
import os
from datetime import datetime, timedelta
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.db import close_old_connections
from django.db.models import Count
from django.db.models.functions import TruncDate
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .models import EmailLog


# --- 1. Dashboard View ---
def dashboard_view(request):
    return render(request, 'dashboard.html')


# --- 2. Helper Function for Email Sending (SMTP) ---
def send_emails_task(recipient_data, subject, body, is_html=True):
    close_old_connections()

    # Gmail SMTP Settings
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = "premdemo22@gmail.com"
    sender_password = os.environ.get('GMAIL_PASSWORD')

    try:
        # Server connect karein
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)

        for data in recipient_data:
            try:
                email = data.get('email')

                # Personalization logic
                personalized_body = body
                for key, value in data.items():
                    if key != 'email':
                        personalized_body = personalized_body.replace(f"{{{{{key}}}}}", str(value))

                # Database mein log banayein
                log = EmailLog.objects.create(email_address=email, status='Unread', deliverability='Sent')

                # Tracking Pixel
                pixel_url = f"https://trekemail-python.onrender.com/track/{log.id}.png"
                full_body = f"{personalized_body} <img src='{pixel_url}' width='1' height='1' />"

                # Email prepare karein
                msg = MIMEMultipart()
                msg['From'] = f"Prem Yadav <{sender_email}>"
                msg['To'] = email
                msg['Subject'] = subject
                msg['Reply-To'] = sender_email

                msg.attach(MIMEText(full_body, 'html' if is_html else 'plain'))

                # Mail bhejein
                server.sendmail(sender_email, email, msg.as_string())
                time.sleep(1)  # Gmail limit ka dhyan rakhein
            except Exception as e:
                print(f"Error sending to {email}: {e}")

        server.quit()
    except Exception as e:
        print(f"SMTP Server Error: {e}")


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
            content_format = request.POST.get('format', 'html')

            if csv_file:
                df = pd.read_csv(csv_file)
                if 'email' not in df.columns:
                    return Response({"error": "CSV must have 'email' column"}, status=400)
                recipients = df.to_dict('records')
            else:
                recipients = [{'email': manual_email}]

            send_emails_task(recipients, subject, body, is_html=(content_format == 'html'))
            return JsonResponse({"status": "Success"})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# --- 6. Stats API ---
class DashboardStatsView(APIView):
    def get(self, request):
        logs_queryset = EmailLog.objects.all().order_by('-created_at')
        seven_days_ago = timezone.now().date() - timedelta(days=7)

        return Response({
            "stats": {
                "total_sent": logs_queryset.count(),
                "inbox_count": logs_queryset.filter(deliverability='Inbox').count(),
                "spam_count": logs_queryset.filter(deliverability='Spam').count(),
                "read_count": logs_queryset.filter(status='Read').count(),
                "unread_count": logs_queryset.filter(status='Unread').count(),
            },
            "date_stats": list(EmailLog.objects.filter(created_at__date__gte=seven_days_ago)
                               .values('created_at__date')
                               .annotate(date=TruncDate('created_at'), count=Count('id'))
                               .order_by('-date')),
            "logs": [{
                'email_address': log.email_address,
                'status': log.deliverability,
                'mark': log.status,
                'deliverability': log.deliverability,
                'date_sent': timezone.localtime(log.created_at).strftime('%Y-%m-%d %H:%M')
            } for log in logs_queryset[:20]]
        })