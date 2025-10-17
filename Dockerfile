# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY offshore_detector/requirements.txt .
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential python3-dev && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install gunicorn && \
    apt-get purge -y --auto-remove build-essential python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy the rest of the application code
COPY offshore_detector/ /app/

# Make port 8081 available to the world outside this container
EXPOSE 8081

# Define environment variable
ENV FLASK_APP app

# Run the app using gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8081", "--workers", "1", "--worker-class", "gevent", "--timeout", "300", "app:app"]
