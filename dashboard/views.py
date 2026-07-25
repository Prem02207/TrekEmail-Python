import pandas as pd
import base64
import threading
import time
import smtplib
import os
from datetime import datetime
import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from core.db import email_collection  # MongoDB connection import


# --- 1. Background Task for Email Sending (Brevo Configured & MongoDB Logging) ---
def send_emails_task(recipient_data, subject, body, is_html=True):
    def _run_email_task():
        smtp_server = "smtp-brevo.com"
        smtp_port = 2525
        sender_email = os.environ.get('EMAIL_HOST_USER')
        sender_password = os.environ.get('EMAIL_HOST_PASSWORD')

        if not sender_email or not sender_password:
            print("ERROR: Brevo credentials missing in environment variables!")
            return

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

                    # Generate unique ID for MongoDB tracking
                    email_id = str(uuid.uuid4())

                    # Insert log into MongoDB
                    email_collection.insert_one({
                        "emailId": email_id,
                        "email_address": email,
                        "subject": subject,
                        "status": "Unread",
                        "deliverability": "Sent",
                        "createdAt": datetime.utcnow()
                    })

                    pixel_url = f"https://trekemail-python.onrender.com/track/{email_id}.png"
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


# --- 3. Filtered Logs API (MongoDB) ---
class FilteredLogsView(APIView):
    def get(self, request):
        selected_date = request.query_params.get('date')
        if not selected_date:
            return Response({"error": "Date required"}, status=400)

        # Querying MongoDB based on date string (YYYY-MM-DD)
        start_date = f"{selected_date}T00:00:00.000Z"
        end_date = f"{selected_date}T23:59:59.999Z"

        query = {
            "createdAt": {
                "$gte": datetime.fromisoformat(start_date[:-1]),
                "$lte": datetime.fromisoformat(end_date[:-1])
            }
        }

        logs_cursor = email_collection.find(query).sort("createdAt", -1)
        logs_list = list(logs_cursor)

        stats = {
            "total_sent": len(logs_list),
            "read_count": sum(1 for log in logs_list if log.get('status') == 'Read'),
            "unread_count": sum(1 for log in logs_list if log.get('status') == 'Unread'),
            "inbox_count": sum(1 for log in logs_list if log.get('deliverability') == 'Inbox'),
            "spam_count": sum(1 for log in logs_list if log.get('deliverability') == 'Spam'),
        }

        logs = [{
            'email_address': log.get('email_address'),
            'status': 'Sent',
            'mark': log.get('status'),
            'deliverability': log.get('deliverability', 'Sent'),
            'date_sent': log.get('createdAt').strftime('%Y-%m-%d %H:%M') if log.get('createdAt') else 'N/A'
        } for log in logs_list[:20]]

        return Response({"logs": logs, "stats": stats})


# --- 4. Tracking Pixel (MongoDB Updated) ---
class TrackEmailView(APIView):
    def get(self, request, log_id):
        gif_data = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
        try:
            clean_id = log_id.replace('.png', '')
            # Update status in MongoDB if found and unread
            email_collection.update_one(
                {"emailId": clean_id, "status": "Unread"},
                {"$set": {"status": "Read"}}
            )
        except Exception as e:
            print(f"Tracking error: {e}")

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


# --- 6. Stats API (MongoDB Aggregation) ---
class DashboardStatsView(APIView):
    def get(self, request):
        all_logs = list(email_collection.find().sort("createdAt", -1))

        stats = {
            "total_sent": len(all_logs),
            "inbox_count": sum(1 for log in all_logs if log.get('deliverability') == 'Inbox'),
            "spam_count": sum(1 for log in all_logs if log.get('deliverability') == 'Spam'),
            "read_count": sum(1 for log in all_logs if log.get('status') == 'Read'),
            "unread_count": sum(1 for log in all_logs if log.get('status') == 'Unread'),
        }

        logs = [{
            'email_address': log.get('email_address'),
            'status': 'Sent',
            'mark': log.get('status'),
            'deliverability': log.get('deliverability', 'Sent'),
            'date_sent': log.get('createdAt').strftime('%Y-%m-%d %H:%M') if log.get('createdAt') else 'N/A'
        } for log in all_logs[:20]]

        # Grouping by date for chart/stats (last 7 days logic via MongoDB aggregation)
        pipeline = [
            {
                "$project": {
                    "date": {
                        "$dateToString": {"format": "%Y-%m-%d", "date": "$createdAt"}
                    }
                }
            },
            {
                "$group": {
                    "_id": "$date",
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": -1}},
            {"$limit": 7}
        ]

        date_stats_raw = list(email_collection.aggregate(pipeline))
        date_stats = [{"date": item["_id"], "count": item["count"]} for item in date_stats_raw if item["_id"]]

        return Response({
            "stats": stats,
            "logs": logs,
            "date_stats": date_stats
        })