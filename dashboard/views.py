import pandas as pd
import base64
import traceback
import threading
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse
from django.core.mail import EmailMessage, get_connection
from django.db import close_old_connections
from django.db.models.functions import TruncDate
from django.db.models import Count
from .models import EmailLog


# --- 1. Dashboard View ---
def dashboard_view(request):
    emails = EmailLog.objects.all().order_by('-created_at')
    context = {
        'recent_emails': emails,
        'total_sent': emails.filter(status='Sent').count() + emails.filter(status='Read').count(),
        'inbox': emails.filter(deliverability='Inbox').count(),
        'spam': emails.filter(deliverability='Spam').count(),
        'read': emails.filter(status='Read').count(),
        'unread': emails.filter(status='Sent').count(),
    }
    return render(request, 'dashboard.html', context)


# --- 2. Dashboard Stats API (Updated to handle 'all') ---
class DashboardStatsView(APIView):
    def get(self, request):
        try:
            selected_date = request.query_params.get('date')
            logs = EmailLog.objects.all()

            # Agar date di hai aur 'all' nahi hai, toh filter karo
            if selected_date and selected_date != 'all':
                logs = logs.filter(created_at__date=selected_date)

            # Stats calculate karo
            total = logs.count()
            inbox = logs.filter(deliverability='Inbox').count()
            spam = logs.filter(deliverability='Spam').count()
            read = logs.filter(status='Read').count()
            unread = logs.filter(status='Sent').count()

            # Logs ka limit set karo
            logs_list = logs.order_by('-created_at')[:20]

            # Date stats (Sirf last 7 days)
            date_stats_query = EmailLog.objects.annotate(date=TruncDate('created_at')) \
                .values('date').annotate(count=Count('id')).order_by('-date')[:7]

            date_stats = [{'date': item['date'].strftime('%Y-%m-%d') if item['date'] else 'N/A', 'count': item['count']}
                          for item in date_stats_query]

            return Response({
                "total_sent": total,
                "inbox_count": inbox,
                "spam_count": spam,
                "read_count": read,
                "unread_count": unread,
                "logs": [{
                    'email_address': l.email_address,
                    'status': 'Sent',
                    'deliverability': l.deliverability,
                    'mark': l.status,
                    'date_sent': l.created_at.strftime('%Y-%m-%d')
                } for l in logs_list],
                "date_stats": date_stats
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# --- 3. Filtered Logs API ---
class FilteredLogsView(APIView):
    def get(self, request):
        selected_date = request.query_params.get('date')
        logs_queryset = EmailLog.objects.all().order_by('-created_at')

        if selected_date and selected_date != 'all':
            logs_queryset = logs_queryset.filter(created_at__date=selected_date)

        logs = [
            {'email_address': log.email_address, 'status': 'Sent', 'deliverability': log.deliverability,
             'mark': log.status, 'date_sent': log.created_at.strftime('%Y-%m-%d')}
            for log in logs_queryset[:20]
        ]
        return Response({"logs": logs})


# --- 4. Bulk Email Sending ---
class SendBulkEmailView(APIView):
    def post(self, request):
        try:
            csv_file = request.FILES.get('csv_file')
            manual_email = request.POST.get('manual_email')
            subject = request.POST.get('subject')
            body = request.POST.get('body')
            attachment = request.FILES.get('attachment')

            attach_data = attachment.read() if attachment else None
            attach_name = attachment.name if attachment else None
            attach_type = attachment.content_type if attachment else None

            recipients = pd.read_csv(csv_file).iloc[:, 0].dropna().tolist() if csv_file else [manual_email]

            def send_emails_task(recipient_list, subject, body, attach_data, attach_name, attach_type):
                close_old_connections()
                try:
                    with get_connection() as connection:
                        for email in recipient_list:
                            try:
                                log = EmailLog.objects.create(email_address=email, status='Sent',
                                                              deliverability='Inbox')
                                pixel_url = f"http://127.0.0.1:8000/track/{log.id}.png/"
                                content = f"{body} <img src='{pixel_url}' width='1' height='1' />"
                                msg = EmailMessage(subject, content, settings.DEFAULT_FROM_EMAIL, [email],
                                                   connection=connection)
                                msg.content_subtype = "html"
                                if attach_data: msg.attach(attach_name, attach_data, attach_type)
                                msg.send()
                            except:
                                traceback.print_exc()
                except Exception as e:
                    print(f"DEBUG: Connection Error: {e}")

            threading.Thread(target=send_emails_task,
                             args=(recipients, subject, body, attach_data, attach_name, attach_type),
                             daemon=True).start()
            return Response({"message": "Processing started in background"})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# --- 5. Tracking Pixel ---
class TrackEmailView(APIView):
    def get(self, request, log_id):
        clean_id = str(log_id).replace('.png', '')
        try:
            log = EmailLog.objects.get(id=clean_id)
            if log.status != 'Read':
                log.status = 'Read'
                log.save()
        except:
            pass
        return HttpResponse(base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"),
                            content_type="image/gif")