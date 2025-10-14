"""
Main web application for the Offshore Transaction Risk Detection System.
"""
from flask import Flask, request, render_template, redirect, url_for, flash, send_from_directory
import os
import pandas as pd
from datetime import datetime
from werkzeug.utils import secure_filename

from offshore_detector import process_transactions

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SECRET_KEY'] = os.urandom(24)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def index():
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

            try:
                processed_files = process_transactions(incoming_path, outgoing_path)
                
                return render_template('index.html', processed_files=processed_files)
            except Exception as e:
                flash(f'An error occurred during processing: {e}')
                return redirect(request.url)

    return render_template('index.html')

@app.route('/download/<filename>')
def download_file(filename):
    desktop_path = os.getenv('DESKTOP_PATH', os.path.join(os.path.expanduser('~'), 'Desktop'))
    return send_from_directory(desktop_path, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
