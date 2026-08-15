# Email Automation Agent

A powerful, automated email scheduling and delivery system built with Flask, APScheduler, and SQLAlchemy.

## Features

- **Automated Scheduling**: Schedule emails to be sent at specific dates and times in the future.
- **Bulk Import**: Easily import email tasks from CSV or Excel files.
- **Draft Management**: Save email drafts and edit them before scheduling.
- **Background Processing**: Uses APScheduler to handle email delivery in the background reliably.
- **Task Management**: View, retry, or delete scheduled or failed tasks.
- **Dashboard Statistics**: Get a quick overview of your email queue, including total, pending, scheduled, sending, sent, and failed tasks.
- **Scheduler Control**: Pause, resume, start, or stop the email scheduler directly from the dashboard.

## Prerequisites

- Python 3.8+
- An SMTP email account (e.g., Gmail, Outlook) to send emails. (If using Gmail, it's recommended to use an App Password).

## Setup & Installation

1. **Clone the repository** (if you haven't already):
   ```bash
   git clone <your-repository-url>
   cd email-automation-agent
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   
   # On Windows:
   venv\Scripts\activate
   
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install the dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Create a `.env` file in the root of the project with your SMTP configuration and Flask settings:

   ```env
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your_email@gmail.com
   SMTP_PASSWORD=your_app_password
   FLASK_APP=app.py
   FLASK_ENV=development
   SECRET_KEY=your_secret_key
   ```
   *Note: For Gmail, ensure 2-Step Verification is enabled and use an App Password instead of your regular password.*

## Running the Application

1. Ensure your virtual environment is activated.
2. Run the Flask application:
   ```bash
   python app.py
   ```
3. Open your web browser and navigate to `http://localhost:5000`.

## Project Structure

- `app.py`: The main Flask application containing the web routes and API endpoints.
- `models.py`: Defines the SQLAlchemy database models (`EmailTask`).
- `scheduler.py`: Handles the APScheduler background tasks for sending emails via SMTP.
- `templates/`: Contains the HTML templates for the frontend.
- `static/`: Contains static assets (CSS, JS) for the frontend.
- `instance/`: SQLite database files are automatically generated here.

## API Endpoints

- `GET /api/tasks`: Fetch all email tasks.
- `GET /api/stats`: Fetch statistics on task statuses.
- `POST /api/save`: Save draft emails.
- `POST /api/execute`: Schedule emails for sending.
- `POST /api/import`: Import tasks from CSV/Excel.
- `POST /api/scheduler/control`: Control the scheduler (start, stop, pause, resume).
- `DELETE /api/tasks/<task_id>`: Delete a specific task.
- `POST /api/tasks/retry/<task_id>`: Retry a failed task.

## License

MIT License
