FROM python:3.11-slim

WORKDIR /app

# Install dependencies system
RUN apt-get update && apt-get install -y \
    build-essential \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy all source code
COPY . .

# Cloud Run uses PORT env (default 8080)
EXPOSE 8080

# Jalankan Gunicorn untuk Flask app
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:create_app()"]
