from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class EmailTask(db.Model):
    __tablename__ = 'email_tasks'

    id = db.Column(db.Integer, primary_key=True)
    email_address = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    message_content = db.Column(db.Text, nullable=False)
    scheduled_time = db.Column(db.DateTime, nullable=False)
    actual_send_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='Pending') # Pending, Scheduled, Sending, Sent, Failed
    error_message = db.Column(db.Text, nullable=True)
    retry_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'email_address': self.email_address,
            'subject': self.subject,
            'message_content': self.message_content,
            'scheduled_time': self.scheduled_time.strftime('%Y-%m-%d %H:%M:%S') if self.scheduled_time else None,
            'actual_send_time': self.actual_send_time.strftime('%Y-%m-%d %H:%M:%S') if self.actual_send_time else None,
            'status': self.status,
            'error_message': self.error_message,
            'retry_count': getattr(self, 'retry_count', 0) or 0,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
