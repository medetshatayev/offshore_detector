"""
Main web application for the Offshore Transaction Risk Detection System.
"""
from flask import Flask, request, render_template, redirect, url_for, flash, send_from_directory, session
import os
import pandas as pd
from datetime import datetime

import threading
import uuid
import logging

from offshore_detector import process_transactions

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
# Use environment variable for SECRET_KEY
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# In-memory job store
jobs = {}

def process_transactions_wrapper(job_id, incoming_path, outgoing_path):
    """
    Wrapper to run processing in a thread and update job status.
    Ensures proper cleanup of uploaded files.
    """
    try:
        processed_files = process_transactions(incoming_path, outgoing_path)
        jobs[job_id] = {'status': 'completed', 'files': processed_files}
        logging.info(f"Job {job_id} completed successfully")
    except Exception as e:
        error_msg = str(e)
        jobs[job_id] = {'status': 'failed', 'error': error_msg}
        logging.error(f"Job {job_id} failed: {error_msg}", exc_info=True)
    finally:
        # Clean up uploaded files after processing
        _cleanup_uploaded_files(incoming_path, outgoing_path)


def _cleanup_uploaded_files(*file_paths):
    """
    Clean up uploaded files with proper error handling.
    """
    for path in file_paths:
        if not path:
            continue
        try:
            if os.path.exists(path):
                os.remove(path)
                logging.debug(f"Cleaned up file: {path}")
        except Exception as e:
            logging.warning(f"Failed to clean up file {path}: {e}")

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
            # Validate file extensions
            incoming_filename = os.path.basename(incoming_file.filename)
            outgoing_filename = os.path.basename(outgoing_file.filename)
            
            if not _is_valid_excel_file(incoming_filename):
                flash('Invalid file type for incoming file. Only Excel files (.xlsx, .xls) are allowed.')
                return redirect(request.url)
            
            if not _is_valid_excel_file(outgoing_filename):
                flash('Invalid file type for outgoing file. Only Excel files (.xlsx, .xls) are allowed.')
                return redirect(request.url)
            
            incoming_path = os.path.join(app.config['UPLOAD_FOLDER'], incoming_filename)
            outgoing_path = os.path.join(app.config['UPLOAD_FOLDER'], outgoing_filename)

            incoming_file.save(incoming_path)
            outgoing_file.save(outgoing_path)

            job_id = str(uuid.uuid4())
            session['job_id'] = job_id
            jobs[job_id] = {'status': 'processing'}

            thread = threading.Thread(target=process_transactions_wrapper, args=(job_id, incoming_path, outgoing_path))
            thread.daemon = True  # Allow clean shutdown
            thread.start()
            
            return redirect(url_for('index'))

    return render_template('index.html', job_info=job_info)

@app.route('/reload')
def reload():
    session.pop('job_id', None)
    return redirect(url_for('index'))

@app.route('/download/<filename>')
def download_file(filename):
    # Validate filename to prevent path traversal attacks
    safe_filename = os.path.basename(filename)
    if not safe_filename or safe_filename != filename:
        flash('Invalid filename')
        return redirect(url_for('index'))
    
    desktop_path = os.getenv('DESKTOP_PATH', os.path.join(os.path.expanduser('~'), 'Desktop'))
    file_path = os.path.join(desktop_path, safe_filename)
    
    # Verify the file exists and is within the allowed directory
    if not os.path.exists(file_path) or not os.path.abspath(file_path).startswith(os.path.abspath(desktop_path)):
        flash('File not found')
        return redirect(url_for('index'))
    
    return send_from_directory(desktop_path, safe_filename, as_attachment=True)

def _is_valid_excel_file(filename):
    """
    Validate that a filename has a valid Excel extension.
    """
    if not filename:
        return False
    allowed_extensions = {'.xlsx', '.xls'}
    return any(filename.lower().endswith(ext) for ext in allowed_extensions)


if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug_mode)
