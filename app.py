import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime
from models import db, EmailTask
from scheduler import init_scheduler, schedule_email, scheduler, get_scheduler_status

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scheduler.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Initialize database and scheduler on first request
with app.app_context():
    db.create_all()
    # Migration safeguard: ensure retry_count column exists
    try:
        from sqlalchemy import text
        db.session.execute(text("ALTER TABLE email_tasks ADD COLUMN retry_count INTEGER DEFAULT 0"))
        db.session.commit()
    except Exception:
        db.session.rollback()
    init_scheduler(app)

@app.before_request
def ensure_scheduler():
    if not scheduler.running:
        init_scheduler(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/save', methods=['POST'])
def save_data():
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    saved_tasks = []
    try:
        from datetime import datetime
        for row in data:
            if not row.get('email_address'):
                continue # Skip empty rows
                
            task = EmailTask(
                email_address=row.get('email_address'),
                subject=row.get('subject'),
                message_content=row.get('message_content'),
                scheduled_time=datetime.now(),
                status='Pending'
            )
            db.session.add(task)
            db.session.commit() # Commit individually to get ID, or bulk save
            saved_tasks.append(task.to_dict())
            
        return jsonify({'message': 'Draft saved successfully', 'tasks': saved_tasks})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/execute', methods=['POST'])
def execute_data():
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        from datetime import datetime, timedelta
        # Save and schedule
        for i, row in enumerate(data):
            if not row.get('email_address'):
                continue
                
            scheduled_time = datetime.now() + timedelta(seconds=20 * i)
            
            task = EmailTask(
                email_address=row.get('email_address'),
                subject=row.get('subject'),
                message_content=row.get('message_content'),
                scheduled_time=scheduled_time,
                status='Scheduled'
            )
            db.session.add(task)
            db.session.commit()
            
            schedule_email(app, task)
            
        return jsonify({'message': 'Emails scheduled successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/import', methods=['POST'])
def import_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file, header=None)
        elif file.filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file, header=None)
        else:
            return jsonify({'error': 'Unsupported file format'}), 400

        # Replace NaN with empty string
        df = df.fillna('')
        
        # Convert to list of lists (2D array)
        records = df.values.tolist()
        
        return jsonify({'records': records})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    tasks = EmailTask.query.order_by(EmailTask.created_at.desc()).all()
    return jsonify([t.to_dict() for t in tasks])

@app.route('/api/stats', methods=['GET'])
def get_stats():
    total = EmailTask.query.count()
    pending = EmailTask.query.filter_by(status='Pending').count()
    scheduled = EmailTask.query.filter_by(status='Scheduled').count()
    sending = EmailTask.query.filter_by(status='Sending').count()
    sent = EmailTask.query.filter_by(status='Sent').count()
    failed = EmailTask.query.filter_by(status='Failed').count()
    
    return jsonify({
        'total': total,
        'pending': pending,
        'scheduled': scheduled,
        'sending': sending,
        'sent': sent,
        'failed': failed
    })

@app.route('/api/scheduler/control', methods=['POST'])
def control_scheduler():
    action = request.json.get('action')
    try:
        if action == 'start':
            if not scheduler.running:
                init_scheduler(app)
            elif scheduler.state == 2:  # Paused
                scheduler.resume()
        elif action == 'stop':
            if scheduler.running:
                scheduler.pause()
        elif action == 'pause':
            if scheduler.running:
                scheduler.pause()
        elif action == 'resume':
            if not scheduler.running:
                init_scheduler(app)
            else:
                scheduler.resume()
        else:
            return jsonify({'error': 'Invalid action'}), 400
            
        return jsonify(get_scheduler_status())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scheduler/status', methods=['GET'])
def scheduler_status():
    return jsonify(get_scheduler_status())

@app.route('/api/tasks/all', methods=['DELETE'])
def delete_all_tasks():
    try:
        num_deleted = db.session.query(EmailTask).delete()
        db.session.commit()
        return jsonify({'message': f'Deleted {num_deleted} tasks successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    try:
        task = EmailTask.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        db.session.delete(task)
        db.session.commit()
        return jsonify({'message': 'Task deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/retry/<int:task_id>', methods=['POST'])
def retry_task(task_id):
    try:
        task = db.session.get(EmailTask, task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
            
        data = request.get_json(silent=True) or {}
        new_time_str = data.get('new_time')
        
        task.retry_count = 0  # Reset retry counter on manual retry
        if new_time_str:
            task.scheduled_time = pd.to_datetime(new_time_str).to_pydatetime()
            task.status = 'Scheduled'
        else:
            task.scheduled_time = datetime.now()
            task.status = 'Scheduled'
            
        task.error_message = None
        db.session.commit()
        schedule_email(app, task)
        return jsonify({'message': 'Task rescheduled for retry'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/retry-failed', methods=['POST'])
def retry_all_failed():
    try:
        from datetime import datetime
        failed_tasks = EmailTask.query.filter_by(status='Failed').all()
        for t in failed_tasks:
            t.status = 'Scheduled'
            t.retry_count = 0
            t.scheduled_time = datetime.now()
            t.error_message = None
        db.session.commit()
        init_scheduler(app)
        return jsonify({'message': f'Rescheduled {len(failed_tasks)} failed emails for retry'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
