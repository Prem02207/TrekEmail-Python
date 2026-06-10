from rest_framework.views import APIView
from rest_framework.response import Response
from .models import EmailLog
import pandas as pd
from django.core.mail import EmailMessage, get_connection
from django.conf import settings
from django.http import HttpResponse
from django.db import close_old_connections
from django.db.models.functions import TruncDate
from django.db.models import Count
import base64
import threading
import traceback


class DashboardStatsView(APIView):
    def get(self, request):
        try:
            total = EmailLog.objects.count()
            inbox = EmailLog.objects.filter(deliverability='Inbox').count()
            spam = EmailLog.objects.filter(deliverability='Spam').count()
            read = EmailLog.objects.filter(status='Read').count()
            unread = EmailLog.objects.filter(status='Sent').count()

            logs_queryset = EmailLog.objects.all().order_by('-created_at')[:10]
            logs = [
                {
                    'email_address': log.email_address,
                    'status': 'Sent',
                    'deliverability': log.deliverability,
                    'mark': log.status,
                    'date_sent': log.created_at.strftime('%Y-%m-%d')
                } for log in logs_queryset
            ]

            date_stats_query = EmailLog.objects.annotate(date=TruncDate('created_at')) \
                .values('date').annotate(count=Count('id')).order_by('-date')

            date_stats = [
                {'date': item['date'].strftime('%Y-%m-%d') if item['date'] else 'N/A', 'count': item['count']}
                for item in date_stats_query
            ]

            return Response({
                "total_sent": total,
                "inbox_count": inbox,
                "spam_count": spam,
                "read_count": read,
                "unread_count": unread,
                "logs": logs,
                "date_stats": date_stats
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class SendBulkEmailView(APIView):
    def post(self, request):
        try:
            csv_file = request.FILES.get('csv_file')
            manual_email = request.POST.get('manual_email')
            subject = request.POST.get('subject')
            body = request.POST.get('body')
            attachment = request.FILES.get('attachment')

            # Attachment ko read karna (Memory management)
            attach_data = attachment.read() if attachment else None
            attach_name = attachment.name if attachment else None
            attach_type = attachment.content_type if attachment else None

            recipients = []
            if csv_file:
                # Pandas se CSV read karna
                df = pd.read_csv(csv_file)
                # Yahan dhyan rakhein ki CSV mein 'email' naam ka column hona chahiye
                recipients = df['email'].dropna().tolist()
            elif manual_email:
                recipients = [manual_email]
            else:
                return Response({"error": "No recipients provided"}, status=400)

            def send_emails_task(recipient_list, subject, body, attach_data, attach_name, attach_type):
                close_old_connections()
                with get_connection() as connection:
                    for email in recipient_list:
                        try:
                            log = EmailLog.objects.create(
                                email_address=email,
                                status='Sent',
                                deliverability='Inbox'
                            )
                            pixel_url = f"http://127.0.0.1:8000/track/{log.id}.png/"
                            content = f"{body} <img src='{pixel_url}' width='1' height='1' style='display:none;' />"

                            msg = EmailMessage(
                                subject, content, settings.DEFAULT_FROM_EMAIL, [email],
                                connection=connection
                            )
                            msg.content_subtype = "html"
                            # Attachment attach karna
                            if attach_data:
                                msg.attach(attach_name, attach_data, attach_type)
                            msg.send()
                        except Exception:
                            traceback.print_exc()

            threading.Thread(target=send_emails_task,
                             args=(recipients, subject, body, attach_data, attach_name, attach_type),
                             daemon=True).start()

            return Response({"message": "Processing started in background"})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class TrackEmailView(APIView):
    def get(self, request, log_id):
        clean_id = str(log_id).replace('.png', '')
        try:
            log = EmailLog.objects.get(id=clean_id)
            if log.status != 'Read':
                log.status = 'Read'
                log.save()
        except EmailLog.DoesNotExist:
            pass

        pixel = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
        return HttpResponse(pixel, content_type="image/gif")