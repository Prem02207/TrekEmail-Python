import os
import pandas as pd
import base64
import traceback
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse
from django.db import close_old_connections
from django.db.models import Count
from django.db.models.functions import TruncDate
from .models import EmailLog


# --- 1. Dashboard View ---
def dashboard_view(request):
    try:
        emails = EmailLog.objects.all()
        email_stats = EmailLog.objects.annotate(date=TruncDate('created_at')).values('date').annotate(
            count=Count('id')).order_by('-date')
        context = {
            'total_sent': emails.filter(status='Sent').count() + emails.filter(status='Read').count(),
            'inbox': emails.filter(deliverability='Inbox').count(),
            'spam': emails.filter(deliverability='Spam').count(),
            'unread': emails.filter(status='Sent').count(),
            'read': emails.filter(status='Read').count(),
            'recent_emails': emails.order_by('-created_at'),
            'email_stats': email_stats
        }
        return render(request, 'dashboard.html', context)
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)


# --- 2. Dashboard Stats API ---
class DashboardStatsView(APIView):
    def get(self, request):
        try:
            emails = EmailLog.objects.all()
            return Response({
                "total_sent": emails.filter(status='Sent').count() + emails.filter(status='Read').count(),
                "inbox_count": emails.filter(deliverability='Inbox').count(),
                "spam_count": emails.filter(deliverability='Spam').count(),
                "read_count": emails.filter(status='Read').count(),
                "unread_count": emails.filter(status='Sent').count(),
                "logs": [
                    {
                        'email_address': log.email_address,
                        'status': log.status,
                        'deliverability': log.deliverability,
                        'date_sent': log.created_at.strftime('%Y-%m-%d')
                    } for log in emails.order_by('-created_at')[:10]
                ]
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# --- 3. Bulk Email Sending View (API Based) ---
class SendBulkEmailView(APIView):
    def post(self, request):
        try:
            domain = request.build_absolute_uri('/')[:-1]
            csv_file = request.FILES.get('csv_file')
            manual_email = request.POST.get('manual_email')
            subject = request.POST.get('subject')
            body = request.POST.get('body')
            attachment = request.FILES.get('attachment')

            # Email list collect karo
            recipients = pd.read_csv(csv_file).iloc[:, 0].dropna().tolist() if csv_file else [manual_email]

            url = "https://api.brevo.com/v3/smtp/email"
            headers = {
                "accept": "application/json",
                "api-key": settings.EMAIL_HOST_PASSWORD,  # Render se load hogi
                "content-type": "application/json"
            }

            for email in recipients:
                close_old_connections()
                log = EmailLog.objects.create(email_address=email, status='Sent', deliverability='Inbox')
                pixel_url = f"{domain}/track/{log.id}.png/"
                content = f"{body} <img src='{pixel_url}' width='1' height='1' />"

                payload = {
                    "sender": {"name": "Prem Yadav", "email": settings.DEFAULT_FROM_EMAIL},
                    "to": [{"email": email}],
                    "subject": subject,
                    "htmlContent": content
                }

                if attachment:
                    payload["attachment"] = [{
                        "name": attachment.name,
                        "content": base64.b64encode(attachment.read()).decode('utf-8')
                    }]

                # API Call
                response = requests.post(url, json=payload, headers=headers)
                print(f"DEBUG: Status for {email}: {response.status_code} - {response.text}")

                if response.status_code != 201:
                    print(f"ERROR: Failed to send to {email}: {response.text}")

            return Response({"message": "Campaign finished successfully"})
        except Exception as e:
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)


# --- 4. Tracking Pixel View ---
class TrackEmailView(APIView):
    def get(self, request, log_id):
        try:
            log = EmailLog.objects.get(id=log_id.replace('.png', ''))
            if log.status != 'Read':
                log.status = 'Read'
                log.save()
        except:
            pass
        return HttpResponse(base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"),
                            content_type="image/gif")