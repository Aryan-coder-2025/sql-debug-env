# Use official Python base image
FROM python:3.12-slim

# Set working directory inside container
WORKDIR /app

# Copy requirements first (for Docker cache efficiency)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files into container
COPY . .

# Expose port 7860 (HuggingFace Spaces uses this port)
EXPOSE 7860

# Command to run the app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]