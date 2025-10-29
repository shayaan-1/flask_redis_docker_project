import os
import random
import time
from flask import (
    Flask,
    request,
    render_template,
    session,
    flash,
    redirect,
    url_for,
    jsonify,
)
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from celery import Celery


app = Flask(__name__)
app.config['SECRET_KEY'] = 'top-secret!'

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.googlemail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = 'flask@example.com'

# PostgreSQL configuration
# PostgreSQL configuration
if os.getenv("GITHUB_ACTIONS"):
    # GitHub Actions uses 'localhost' for PostgreSQL service
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        'postgresql://postgres:postgres@localhost:5432/flaskdb'
    )
else:
    # Local Docker or dev environment uses 'db'
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        'postgresql://postgres:postgres@db:5432/flaskdb'
    )

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Celery configuration
app.config['CELERY_BROKER_URL'] = 'redis://redis:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://redis:6379/0'

# Initialize extensions
mail = Mail(app)
db = SQLAlchemy(app)

# Initialize Celery
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)


class EmailRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, server_default=db.func.now())


@celery.task
def send_async_email(email_data):
    msg = Message(
        email_data['subject'],
        sender=app.config['MAIL_DEFAULT_SENDER'],
        recipients=[email_data['to']],
    )
    msg.body = email_data['body']

    with app.app_context():
        record = EmailRecord(
            email=email_data['to'],
            subject=email_data['subject'],
            body=email_data['body'],
        )
        db.session.add(record)
        db.session.commit()
        mail.send(msg)


@celery.task(bind=True)
def long_task(self):
    """Background task that runs a long function with progress reports."""
    verbs = ['Starting up', 'Booting', 'Repairing', 'Loading', 'Checking']
    adjectives = ['master', 'radiant', 'silent', 'harmonic', 'fast']
    nouns = ['solar array', 'particle reshaper', 'cosmic ray', 'orbiter']
    message = ''
    total = random.randint(10, 50)
    for i in range(total):
        if not message or random.random() < 0.25:
            message = '{0} {1} {2}...'.format(
                random.choice(verbs),
                random.choice(adjectives),
                random.choice(nouns),
            )
        self.update_state(
            state='PROGRESS',
            meta={'current': i, 'total': total, 'status': message},
        )
        time.sleep(1)
    return {
        'current': 100,
        'total': 100,
        'status': 'Task completed!',
        'result': 42,
    }


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template('index.html', email=session.get('email', ''))

    email = request.form['email']
    session['email'] = email

    email_data = {
        'subject': 'Hello from Flask',
        'to': email,
        'body': (
            'This is a test email sent from a background '
            'Celery task.'
        ),
    }

    if request.form['submit'] == 'Send':
        send_async_email.delay(email_data)
        flash(f'Sending email to {email}')
    else:
        send_async_email.apply_async(
            args=[email_data],
            countdown=60,
        )
        flash(f'An email will be sent to {email} in one minute')

    return redirect(url_for('index'))


@app.route('/longtask', methods=['POST'])
def longtask():
    task = long_task.apply_async()
    return jsonify({}), 202, {
        'Location': url_for('taskstatus', task_id=task.id),
    }


@app.route('/status/<task_id>')
def taskstatus(task_id):
    task = long_task.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'current': 0,
            'total': 1,
            'status': 'Pending...',
        }
    elif task.state != 'FAILURE':
        response = {
            'state': task.state,
            'current': task.info.get('current', 0),
            'total': task.info.get('total', 1),
            'status': task.info.get('status', ''),
        }
        if 'result' in task.info:
            response['result'] = task.info['result']
    else:
        response = {
            'state': task.state,
            'current': 1,
            'total': 1,
            'status': str(task.info),
        }
    return jsonify(response)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
