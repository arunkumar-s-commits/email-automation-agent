import smtplib
from email.message import EmailMessage
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app
import os

scheduler = BackgroundScheduler()

def init_scheduler(app):
    scheduler.start()
    app.logger.info("Scheduler started.")

def send_email_job(app, task_id):
    """
    Background job to send an email. We need to pass the app context
    so that SQLAlchemy can access the database.
    """
    with app.app_context():
        from models import db, EmailTask
        
        task = EmailTask.query.get(task_id)
        if not task:
            app.logger.error(f"Task {task_id} not found.")
            return

        # Double check status
        if task.status != 'Scheduled':
            app.logger.warning(f"Task {task_id} is in status {task.status}, skipping.")
            return

        task.status = 'Sending'
        db.session.commit()

        smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        smtp_user = os.environ.get('SMTP_USER')
        smtp_password = os.environ.get('SMTP_PASSWORD')

        if not smtp_user or not smtp_password:
            task.status = 'Failed'
            task.error_message = 'SMTP credentials not configured.'
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
            with smtplib.SMTP(smtp_server, smtp_port) as server:
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
            task.error_message = str(e)
            db.session.commit()
            app.logger.error(f"Task {task_id} failed to send: {str(e)}")

def schedule_email(app, task):
    """
    Add a task to the scheduler.
    """
    scheduler.add_job(
        func=send_email_job,
        trigger='date',
        run_date=task.scheduled_time,
        args=[app, task.id],
        id=f'email_task_{task.id}',
        replace_existing=True
    )
    app.logger.info(f"Job scheduled for task {task.id} at {task.scheduled_time}")

def get_scheduler_status():
    return {
        "running": scheduler.running,
        "state": scheduler.state # 0=STOPPED, 1=RUNNING, 2=PAUSED
    }
