# Use the official Python image as the base image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the requirements and app files
COPY requirements.txt .
COPY app.py .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create the storage directory
RUN mkdir storage

# Expose the application port
EXPOSE 5000

# Start the Flask application
CMD ["python", "app.py"]
