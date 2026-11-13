import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app
import os

scheduler = BackgroundScheduler()

def process_email_queue(app):
    """
    Continuous background worker job.
    1. First processes all Scheduled emails whose scheduled_time has arrived.
    2. Once ALL scheduled emails have completed sending:
       Checks for any failed emails (status == 'Failed' and retry_count < MAX_RETRIES)
       and automatically retries sending them continuously until completion.
    """
    with app.app_context():
        from models import db, EmailTask
        now = datetime.now()

        # Step 1: Recover any tasks stuck in 'Sending' for more than 5 minutes (ungraceful crash)
        stuck_tasks = EmailTask.query.filter(
            EmailTask.status == 'Sending',
            EmailTask.scheduled_time <= now - timedelta(minutes=5)
        ).all()
        for stuck in stuck_tasks:
            stuck.status = 'Scheduled'
        if stuck_tasks:
            db.session.commit()

        # Step 2: Pick the oldest due 'Scheduled' task
        due_task = EmailTask.query.filter(
            EmailTask.status == 'Scheduled',
            EmailTask.scheduled_time <= now
        ).order_by(EmailTask.scheduled_time.asc()).first()

        if due_task:
            send_email_job(app, due_task.id)
            return

        # Step 3: Check if there are other regular tasks still scheduled for the future
        has_future_scheduled = EmailTask.query.filter(
            EmailTask.status.in_(['Scheduled', 'Sending'])
        ).first()

        if has_future_scheduled:
            # Main scheduled batch still in progress; wait for it to complete
            return

        # Step 4: All regular scheduled emails have finished!
        # Automatically check for failed emails and continuously retry them
        MAX_RETRIES = 3
        failed_task = EmailTask.query.filter(
            EmailTask.status == 'Failed',
            EmailTask.retry_count < MAX_RETRIES
        ).order_by(EmailTask.id.asc()).first()

        if failed_task:
            failed_task.retry_count = (failed_task.retry_count or 0) + 1
            app.logger.info(
                f"[Auto-Retry] Retrying failed email #{failed_task.id} to {failed_task.email_address} "
                f"(Attempt {failed_task.retry_count}/{MAX_RETRIES})"
            )
            # Temporarily mark Scheduled and dispatch immediately
            failed_task.status = 'Scheduled'
            db.session.commit()
            send_email_job(app, failed_task.id)

def init_scheduler(app):
    """
    Initializes and starts the BackgroundScheduler, registering the queue processor.
    """
    if not scheduler.running:
        try:
            scheduler.start()
            app.logger.info("Scheduler background thread started.")
        except Exception as e:
            app.logger.warning(f"Scheduler start notice: {e}")

    # Register continuous queue-processor interval job (runs every 5 seconds)
    if not scheduler.get_job('process_email_queue'):
        scheduler.add_job(
            func=process_email_queue,
            trigger='interval',
            seconds=5,
            args=[app],
            id='process_email_queue',
            replace_existing=True,
            max_instances=1
        )
        app.logger.info("Registered process_email_queue background job.")

def send_email_job(app, task_id):
    """
    Background job to send an email. We need to pass the app context
    so that SQLAlchemy can access the database.
    """
    with app.app_context():
        from models import db, EmailTask
        
        task = db.session.get(EmailTask, task_id)
        if not task:
            app.logger.error(f"Task {task_id} not found.")
            return

        # Double check status
        if task.status != 'Scheduled':
            app.logger.warning(f"Task {task_id} is in status {task.status}, skipping.")
            return

        task.status = 'Sending'
        db.session.commit()

        # Check for HTTP-based Email APIs (HTTPS port 443 - never blocked by cloud firewalls like Render Free Tier)
        resend_api_key = os.environ.get('RESEND_API_KEY')
        brevo_api_key = os.environ.get('BREVO_API_KEY')

        if resend_api_key:
            try:
                import json, urllib.request
                app.logger.info(f"Sending task {task_id} via Resend HTTP API")
                sender = os.environ.get('SMTP_USER') or os.environ.get('RESEND_FROM') or 'onboarding@resend.dev'
                payload = {
                    "from": sender,
                    "to": [task.email_address],
                    "subject": task.subject,
                    "text": task.message_content
                }
                req = urllib.request.Request(
                    "https://api.resend.com/emails",
                    data=json.dumps(payload).encode('utf-8'),
                    headers={
                        "Authorization": f"Bearer {resend_api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "EmailAutomationAgent/1.0"
                    }
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    pass
                task.status = 'Sent'
                task.actual_send_time = datetime.now()
                task.error_message = None
                db.session.commit()
                app.logger.info(f"Task {task_id} sent successfully via Resend.")
                return
            except Exception as e:
                task.status = 'Failed'
                task.error_message = f"Resend API error: {str(e)}"
                db.session.commit()
                app.logger.error(f"Task {task_id} failed via Resend: {str(e)}")
                return

        if brevo_api_key:
            try:
                import json, urllib.request
                app.logger.info(f"Sending task {task_id} via Brevo HTTP API")
                sender_email = os.environ.get('SMTP_USER') or 'noreply@yourdomain.com'
                payload = {
                    "sender": {"email": sender_email, "name": "Email Automation"},
                    "to": [{"email": task.email_address}],
                    "subject": task.subject,
                    "textContent": task.message_content
                }
                req = urllib.request.Request(
                    "https://api.brevo.com/v3/smtp/email",
                    data=json.dumps(payload).encode('utf-8'),
                    headers={
                        "api-key": brevo_api_key,
                        "Content-Type": "application/json",
                        "User-Agent": "EmailAutomationAgent/1.0"
                    }
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    pass
                task.status = 'Sent'
                task.actual_send_time = datetime.now()
                task.error_message = None
                db.session.commit()
                app.logger.info(f"Task {task_id} sent successfully via Brevo.")
                return
            except Exception as e:
                task.status = 'Failed'
                task.error_message = f"Brevo API error: {str(e)}"
                db.session.commit()
                app.logger.error(f"Task {task_id} failed via Brevo: {str(e)}")
                return

        # Fallback to standard SMTP
        smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        smtp_user = os.environ.get('SMTP_USER')
        smtp_password = os.environ.get('SMTP_PASSWORD')

        if not smtp_user or not smtp_password:
            task.status = 'Failed'
            task.retry_count = 3  # Avoid infinite retries if credentials aren't set
            task.error_message = 'SMTP credentials not configured. Please set SMTP_USER and SMTP_PASSWORD in Environment Variables.'
            db.session.commit()
            app.logger.error(f"Task {task_id} failed: SMTP credentials not configured.")
            return

        try:
            msg = EmailMessage()
            msg.set_content(task.message_content)
            msg['Subject'] = task.subject
            msg['From'] = smtp_user
            msg['To'] = task.email_address

            app.logger.info(f"Connecting to SMTP {smtp_server}:{smtp_port} for task {task_id}")
            
            if smtp_port == 465:
                with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30) as server:
                    server.login(smtp_user, smtp_password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                    server.send_message(msg)

            task.status = 'Sent'
            task.actual_send_time = datetime.now()
            task.error_message = None
            db.session.commit()
            app.logger.info(f"Task {task_id} sent successfully.")

        except Exception as e:
            task.status = 'Failed'
            raw_err = str(e)
            if "Network is unreachable" in raw_err or "101" in raw_err:
                friendly_err = "Render Free Tier blocks outbound SMTP ports 587/465. Run locally or use an HTTP API (e.g. Resend/Brevo)."
            elif "timed out" in raw_err.lower() or "110" in raw_err:
                friendly_err = "Connection timed out on SMTP port. Render Free Tier blocks direct SMTP connections."
            else:
                friendly_err = raw_err

            attempt = task.retry_count or 0
            if attempt > 0:
                task.error_message = f"Attempt {attempt}/3 failed: {friendly_err}"
            else:
                task.error_message = friendly_err
            db.session.commit()
            app.logger.error(f"Task {task_id} failed to send: {str(e)}")

def schedule_email(app, task):
    """
    Ensure the scheduler is active.
    The periodic queue processor will pick up the task as soon as
    task.scheduled_time arrives.
    """
    init_scheduler(app)
    # Also add a one-shot trigger as a fast path
    try:
        scheduler.add_job(
            func=send_email_job,
            trigger='date',
            run_date=task.scheduled_time,
            args=[app, task.id],
            id=f'email_task_{task.id}',
            replace_existing=True
        )
    except Exception as e:
        app.logger.warning(f"Could not register direct trigger for task {task.id}: {e}")

def get_scheduler_status():
    return {
        "running": scheduler.running,
        "state": scheduler.state # 0=STOPPED, 1=RUNNING, 2=PAUSED
    }
