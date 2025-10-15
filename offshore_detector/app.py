"""
Main web application for the Offshore Transaction Risk Detection System.
"""
from flask import Flask, request, render_template, redirect, url_for, flash, send_from_directory, session
import os
import pandas as pd
from datetime import datetime
from werkzeug.utils import secure_filename
import threading
import uuid

from offshore_detector import process_transactions

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SECRET_KEY'] = os.urandom(24)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# In-memory job store (for a production environment, consider a more robust solution like Redis)
jobs = {}

def process_transactions_wrapper(job_id, incoming_path, outgoing_path):
    """Wrapper to run processing in a thread and update job status."""
    try:
        processed_files = process_transactions(incoming_path, outgoing_path)
        jobs[job_id] = {'status': 'completed', 'files': processed_files}
    except Exception as e:
        jobs[job_id] = {'status': 'failed', 'error': str(e)}

@app.route('/', methods=['GET', 'POST'])
def index():
    job_id = session.get('job_id')
    job_info = jobs.get(job_id) if job_id else None

    if request.method == 'POST':
        if 'incoming_file' not in request.files or 'outgoing_file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        incoming_file = request.files['incoming_file']
        outgoing_file = request.files['outgoing_file']

        if incoming_file.filename == '' or outgoing_file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        if incoming_file and outgoing_file:
            incoming_filename = secure_filename(incoming_file.filename)
            outgoing_filename = secure_filename(outgoing_file.filename)
            
            incoming_path = os.path.join(app.config['UPLOAD_FOLDER'], incoming_filename)
            outgoing_path = os.path.join(app.config['UPLOAD_FOLDER'], outgoing_filename)

            incoming_file.save(incoming_path)
            outgoing_file.save(outgoing_path)

            job_id = str(uuid.uuid4())
            session['job_id'] = job_id
            jobs[job_id] = {'status': 'processing'}

            thread = threading.Thread(target=process_transactions_wrapper, args=(job_id, incoming_path, outgoing_path))
            thread.start()
            
            return redirect(url_for('index'))

    return render_template('index.html', job_info=job_info)

@app.route('/reload')
def reload():
    session.pop('job_id', None)
    return redirect(url_for('index'))

@app.route('/download/<filename>')
def download_file(filename):
    desktop_path = os.getenv('DESKTOP_PATH', os.path.join(os.path.expanduser('~'), 'Desktop'))
    return send_from_directory(desktop_path, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
