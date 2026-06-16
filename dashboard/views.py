import pandas as pd
import base64
import traceback
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse, JsonResponse  # JsonResponse add kiya
from django.core.mail import EmailMessage, get_connection
from django.db import close_old_connections
from django.db.models.functions import TruncDate
from django.db.models import Count
from .models import EmailLog


# --- Helper Function (Task) ---
def send_emails_task(recipient_list, subject, body, attach_data, attach_name, attach_type):
    close_old_connections()
    try:
        with get_connection() as connection:
            for email in recipient_list:
                try:
                    log = EmailLog.objects.create(email_address=email, status='Sent',
                                                  deliverability='Inbox')
                    # Production mein 127.0.0.1 ki jagah apka live domain aayega
                    pixel_url = f"https://trekemail-python.onrender.com/track/{log.id}.png/"
                    content = f"{body} <img src='{pixel_url}' width='1' height='1' />"
                    msg = EmailMessage(subject, content, settings.DEFAULT_FROM_EMAIL, [email],
                                       connection=connection)
                    msg.content_subtype = "html"
                    if attach_data: msg.attach(attach_name, attach_data, attach_type)
                    msg.send()
                except Exception as e:
                    print(f"Error sending to {email}: {e}")
                    traceback.print_exc()
    except Exception as e:
        print(f"DEBUG: Connection Error: {e}")


# --- 1, 2, 3 (Dashboard/Stats/FilteredLogs) unchanged ---
# (Aapke purane code jaisa hi rahega)

# --- 4. Bulk Email Sending (Updated) ---
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

            # Direct call (Testing ke liye)
            send_emails_task(recipients, subject, body, attach_data, attach_name, attach_type)

            return JsonResponse({"status": "Email processed!"})

        except Exception as e:
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)


# --- 5. Tracking Pixel (Unchanged) ---
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