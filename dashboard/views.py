from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render
from django.core.mail import EmailMessage, get_connection
from django.conf import settings
from django.http import HttpResponse
from django.db import close_old_connections
from django.db.models import Count
from django.db.models.functions import TruncDate
import pandas as pd
import base64
import threading
import traceback
from .models import EmailLog


# --- 1. Template Rendering View ---
def dashboard_view(request):
    emails = EmailLog.objects.all()

    # Date-wise statistics - Yahan humne aapka naya logic integrate kiya hai
    email_stats = EmailLog.objects.annotate(date=TruncDate('created_at')).values('date').annotate(
        count=Count('id')).order_by('-date')

    context = {
        'total_sent': emails.filter(status='Sent').count() + emails.filter(status='Read').count(),
        'inbox': emails.filter(deliverability='Inbox').count(),
        'spam': emails.filter(deliverability='Spam').count(),
        'unread': emails.filter(status='Sent').count(),
        'read': emails.filter(status='Read').count(),
        'recent_emails': emails.order_by('-created_at'),
        'email_stats': email_stats  # Yahan context mein pass kar diya
    }
    return render(request, 'dashboard.html', context)


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
                        'mark': log.status,
                        'date_sent': log.created_at.strftime('%Y-%m-%d')
                    } for log in emails.order_by('-created_at')[:10]
                ]
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# --- 3. Bulk Email Sending View ---
class SendBulkEmailView(APIView):
    def post(self, request):
        try:
            domain = request.build_absolute_uri('/')[:-1]
            csv_file = request.FILES.get('csv_file')
            manual_email = request.POST.get('manual_email')
            subject = request.POST.get('subject')
            body = request.POST.get('body')
            attachment = request.FILES.get('attachment')

            attach_data = attachment.read() if attachment else None
            attach_name = attachment.name if attachment else None
            attach_type = attachment.content_type if attachment else None

            recipients = pd.read_csv(csv_file).iloc[:, 0].dropna().tolist() if csv_file else [manual_email]

            def send_emails_task(recipient_list, subject, body, attach_data, attach_name, attach_type, domain):
                try:
                    close_old_connections()
                    with get_connection() as connection:
                        for email in recipient_list:
                            try:
                                print(f"Attempting to send to {email}")
                                log = EmailLog.objects.create(email_address=email, status='Sent',
                                                              deliverability='Inbox')
                                pixel_url = f"{domain}/track/{log.id}.png/"
                                content = f"{body} <img src='{pixel_url}' width='1' height='1' />"

                                msg = EmailMessage(subject, content, settings.DEFAULT_FROM_EMAIL, [email],
                                                   connection=connection)
                                msg.content_subtype = "html"
                                if attach_data:
                                    msg.attach(attach_name, attach_data, attach_type)

                                msg.send()
                                print(f"Success sent to {email}")
                            except Exception as e:
                                print(f"Error sending to {email}: {e}")
                except Exception as e:
                    print(f"Connection Error: {e}")

            threading.Thread(target=send_emails_task,
                             args=(recipients, subject, body, attach_data, attach_name, attach_type, domain),
                             daemon=True).start()
            return Response({"message": "Processing started in background"})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# --- 4. Tracking Pixel View ---
class TrackEmailView(APIView):
    def get(self, request, log_id):
        try:
            log = EmailLog.objects.get(id=log_id.replace('.png', ''))
            if log.status != 'Read':
                log.status = 'Read'
                log.save()
        except EmailLog.DoesNotExist:
            pass
        return HttpResponse(base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"),
                            content_type="image/gif")