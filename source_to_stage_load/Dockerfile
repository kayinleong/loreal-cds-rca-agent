# Use the official lightweight Python image.
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080


# Set working directory
WORKDIR /app
COPY source_to_stage_load/requirements.txt .

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt


COPY source_to_stage_load/cloud_run/ ./source_to_stage_load/cloud_run

WORKDIR /app/source_to_stage_load/cloud_run

ENV PYTHONPATH=/app/source_to_stage_load/cloud_run


CMD ["gunicorn", "--timeout", "3599", "-b", ":8080", "app:app"]
