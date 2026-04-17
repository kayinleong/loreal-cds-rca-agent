# Use the official lightweight Python image.
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080


# Set working directory
WORKDIR /app
COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt


COPY staging_to_target_load/cloud_run_sp/ ./staging_to_target_load/cloud_run_sp

WORKDIR /app/staging_to_target_load/cloud_run_sp

ENV PYTHONPATH=/app/staging_to_target_load/cloud_run_sp


CMD ["gunicorn", "--timeout", "3599", "-b", ":8080", "app:app"]