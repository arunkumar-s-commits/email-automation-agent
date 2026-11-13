import os

# Gunicorn configuration for Render deployment
workers = 1
threads = 4
timeout = 120

def post_fork(server, worker):
    """
    Called just after a worker has been forked.
    Guarantees the APScheduler background thread starts inside the worker process.
    """
    server.log.info("Worker %s spawned, starting email scheduler...", worker.pid)
    try:
        from app import app
        from scheduler import init_scheduler
        with app.app_context():
            init_scheduler(app)
        server.log.info("Email scheduler initialized in worker %s", worker.pid)
    except Exception as e:
        server.log.error("Failed to initialize scheduler in worker %s: %s", worker.pid, e)

