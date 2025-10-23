"""
FastAPI web application for offshore transaction detection.
Provides upload interface and download endpoints.
"""
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
import uuid
import logging
from typing import Dict
from datetime import datetime
import shutil

from processor import process_transactions
from config import DESKTOP_PATH


# Initialize FastAPI app
app = FastAPI(
    title="Offshore Transaction Risk Detection",
    description="Production-ready offshore transaction detection for Kazakhstani banks",
    version="1.0.0"
)

# In-memory job store
jobs: Dict[str, dict] = {}

# Upload folder
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '/tmp/offshore_uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DESKTOP_PATH, exist_ok=True)


def cleanup_upload_files(*file_paths):
    """
    Clean up uploaded files with safety checks.
    Only removes files within the upload directory.
    """
    upload_folder_abs = os.path.abspath(UPLOAD_FOLDER)
    
    for path in file_paths:
        if not path:
            continue
        
        try:
            abs_path = os.path.abspath(path)
            
            # Security check: ensure file is within upload folder
            if not abs_path.startswith(upload_folder_abs):
                logging.warning(f"Refusing to delete file outside upload folder: {path}")
                continue
            
            if os.path.exists(abs_path):
                os.remove(abs_path)
                logging.debug(f"Cleaned up file: {abs_path}")
                
        except Exception as e:
            logging.warning(f"Failed to clean up file {path}: {e}")


async def process_in_background(job_id: str, incoming_path: str, outgoing_path: str):
    """
    Background task to process transactions.
    Updates job status in the jobs dict.
    """
    try:
        logging.info(f"Starting background processing for job {job_id}")
        processed_files = process_transactions(incoming_path, outgoing_path)
        jobs[job_id] = {
            'status': 'completed',
            'files': processed_files,
            'completed_at': datetime.now().isoformat()
        }
        logging.info(f"Job {job_id} completed successfully")
    except Exception as e:
        error_msg = str(e)
        jobs[job_id] = {
            'status': 'failed',
            'error': error_msg,
            'failed_at': datetime.now().isoformat()
        }
        logging.error(f"Job {job_id} failed: {error_msg}", exc_info=True)
    finally:
        # Clean up uploaded files
        cleanup_upload_files(incoming_path, outgoing_path)


@app.get("/", response_class=HTMLResponse)
async def index():
    """
    Serve the main upload page.
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Offshore Transaction Risk Detection</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }
            
            .container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                max-width: 600px;
                width: 100%;
                padding: 40px;
            }
            
            h1 {
                color: #333;
                font-size: 28px;
                margin-bottom: 10px;
                text-align: center;
            }
            
            .subtitle {
                color: #666;
                text-align: center;
                margin-bottom: 30px;
                font-size: 14px;
            }
            
            .upload-section {
                margin-bottom: 25px;
            }
            
            label {
                display: block;
                color: #333;
                font-weight: 600;
                margin-bottom: 8px;
                font-size: 14px;
            }
            
            input[type="file"] {
                width: 100%;
                padding: 12px;
                border: 2px dashed #667eea;
                border-radius: 10px;
                background: #f8f9ff;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            
            input[type="file"]:hover {
                border-color: #764ba2;
                background: #f0f1ff;
            }
            
            button {
                width: 100%;
                padding: 15px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s ease, box-shadow 0.2s ease;
                margin-top: 20px;
            }
            
            button:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
            }
            
            button:active {
                transform: translateY(0);
            }
            
            button:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }
            
            .status {
                margin-top: 25px;
                padding: 15px;
                border-radius: 10px;
                text-align: center;
                display: none;
            }
            
            .status.processing {
                display: block;
                background: #fff3cd;
                border: 2px solid #ffc107;
                color: #856404;
            }
            
            .status.completed {
                display: block;
                background: #d4edda;
                border: 2px solid #28a745;
                color: #155724;
            }
            
            .status.failed {
                display: block;
                background: #f8d7da;
                border: 2px solid #dc3545;
                color: #721c24;
            }
            
            .download-links {
                margin-top: 15px;
            }
            
            .download-links a {
                display: block;
                padding: 10px;
                margin: 8px 0;
                background: #667eea;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                text-align: center;
                transition: background 0.3s ease;
            }
            
            .download-links a:hover {
                background: #764ba2;
            }
            
            .spinner {
                border: 3px solid #f3f3f3;
                border-top: 3px solid #667eea;
                border-radius: 50%;
                width: 30px;
                height: 30px;
                animation: spin 1s linear infinite;
                margin: 15px auto;
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            
            .info {
                background: #e7f3ff;
                border-left: 4px solid #2196F3;
                padding: 15px;
                margin-top: 25px;
                border-radius: 5px;
                font-size: 13px;
                color: #0c5460;
            }
            
            .info strong {
                display: block;
                margin-bottom: 8px;
                color: #004085;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏦 Offshore Transaction Risk Detection</h1>
            <p class="subtitle">Загрузите файлы Excel для анализа</p>
            
            <form id="uploadForm" enctype="multipart/form-data">
                <div class="upload-section">
                    <label for="incoming_file">Входящие операции (skiprows=4)</label>
                    <input type="file" id="incoming_file" name="incoming_file" accept=".xlsx,.xls" required>
                </div>
                
                <div class="upload-section">
                    <label for="outgoing_file">Исходящие операции (skiprows=5)</label>
                    <input type="file" id="outgoing_file" name="outgoing_file" accept=".xlsx,.xls" required>
                </div>
                
                <button type="submit" id="submitBtn">Начать обработку</button>
            </form>
            
            <div id="status" class="status"></div>
            
            <div class="info">
                <strong>ℹ️ Требования:</strong>
                • Файлы в формате Excel (.xlsx, .xls)<br>
                • Входящие: заголовки с 5-й строки<br>
                • Исходящие: заголовки с 6-й строки<br>
                • Минимальная сумма: 5,000,000 KZT
            </div>
        </div>
        
        <script>
            let jobId = null;
            let pollInterval = null;
            
            document.getElementById('uploadForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData();
                formData.append('incoming_file', document.getElementById('incoming_file').files[0]);
                formData.append('outgoing_file', document.getElementById('outgoing_file').files[0]);
                
                // Disable submit button
                document.getElementById('submitBtn').disabled = true;
                
                // Show processing status
                const statusDiv = document.getElementById('status');
                statusDiv.className = 'status processing';
                statusDiv.innerHTML = '<div class="spinner"></div><p>Обработка файлов...</p>';
                
                try {
                    const response = await fetch('/upload', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        jobId = data.job_id;
                        // Start polling for job status
                        pollInterval = setInterval(checkJobStatus, 2000);
                    } else {
                        throw new Error(data.detail || 'Upload failed');
                    }
                } catch (error) {
                    statusDiv.className = 'status failed';
                    statusDiv.innerHTML = `<p>❌ Ошибка: ${error.message}</p>`;
                    document.getElementById('submitBtn').disabled = false;
                }
            });
            
            async function checkJobStatus() {
                if (!jobId) return;
                
                try {
                    const response = await fetch(`/status/${jobId}`);
                    const data = await response.json();
                    
                    const statusDiv = document.getElementById('status');
                    
                    if (data.status === 'completed') {
                        clearInterval(pollInterval);
                        statusDiv.className = 'status completed';
                        
                        let html = '<p>✅ Обработка завершена!</p>';
                        html += '<div class="download-links">';
                        for (const file of data.files) {
                            html += `<a href="/download/${file}" download>📥 Скачать ${file}</a>`;
                        }
                        html += '</div>';
                        
                        statusDiv.innerHTML = html;
                        document.getElementById('submitBtn').disabled = false;
                        
                    } else if (data.status === 'failed') {
                        clearInterval(pollInterval);
                        statusDiv.className = 'status failed';
                        statusDiv.innerHTML = `<p>❌ Ошибка обработки: ${data.error}</p>`;
                        document.getElementById('submitBtn').disabled = false;
                    }
                } catch (error) {
                    console.error('Status check failed:', error);
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.post("/upload")
async def upload_files(
    background_tasks: BackgroundTasks,
    incoming_file: UploadFile = File(...),
    outgoing_file: UploadFile = File(...)
):
    """
    Upload two Excel files and start background processing.
    
    Returns:
        Dict with job_id for status polling
    """
    # Validate file extensions
    valid_extensions = {'.xlsx', '.xls'}
    
    incoming_ext = os.path.splitext(incoming_file.filename)[1].lower()
    outgoing_ext = os.path.splitext(outgoing_file.filename)[1].lower()
    
    if incoming_ext not in valid_extensions or outgoing_ext not in valid_extensions:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only Excel files (.xlsx, .xls) are allowed."
        )
    
    # Generate unique job ID and filenames
    job_id = str(uuid.uuid4())
    
    incoming_filename = f"{uuid.uuid4()}{incoming_ext}"
    outgoing_filename = f"{uuid.uuid4()}{outgoing_ext}"
    
    incoming_path = os.path.join(UPLOAD_FOLDER, incoming_filename)
    outgoing_path = os.path.join(UPLOAD_FOLDER, outgoing_filename)
    
    # Save uploaded files
    try:
        with open(incoming_path, "wb") as buffer:
            shutil.copyfileobj(incoming_file.file, buffer)
        
        with open(outgoing_path, "wb") as buffer:
            shutil.copyfileobj(outgoing_file.file, buffer)
        
        logging.info(f"Files uploaded for job {job_id}")
        
    except Exception as e:
        logging.error(f"Failed to save uploaded files: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save files: {str(e)}")
    
    # Initialize job status
    jobs[job_id] = {
        'status': 'processing',
        'started_at': datetime.now().isoformat()
    }
    
    # Start background processing
    background_tasks.add_task(process_in_background, job_id, incoming_path, outgoing_path)
    
    return {
        'job_id': job_id,
        'status': 'processing',
        'message': 'Files uploaded successfully. Processing started.'
    }


@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """
    Get the status of a processing job.
    
    Args:
        job_id: Unique job identifier
    
    Returns:
        Dict with job status and results if completed
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return jobs[job_id]


@app.get("/download/{filename}")
async def download_file(filename: str):
    """
    Download a processed file.
    
    Args:
        filename: Name of the file to download
    
    Returns:
        FileResponse with the requested file
    """
    # Validate filename (prevent path traversal)
    safe_filename = os.path.basename(filename)
    if safe_filename != filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    file_path = os.path.join(DESKTOP_PATH, safe_filename)
    
    # Check if file exists
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Verify file is within DESKTOP_PATH (security check)
    if not os.path.abspath(file_path).startswith(os.path.abspath(DESKTOP_PATH)):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'openai_configured': bool(os.getenv('OPENAI_API_KEY'))
    }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv('PORT', 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
