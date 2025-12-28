# Use a slim official Python image so pip exists during build
FROM python:3.11-slim

# system deps you might need (add more if pip errors mention missing libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# keep python quiet and unbuffered (good for logs)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# copy and install dependencies first to benefit from docker cache
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# copy full repo
COPY . /app

# default command: run your worker + web server
# (change path only if different)
CMD ["python", "main/trading_app.py"]
