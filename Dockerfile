# Small, official Python base image
FROM python:3.12-slim

# Prevents Python from buffering stdout (so print() shows up immediately)
ENV PYTHONUNBUFFERED=1

# Working directory inside the container
WORKDIR /app

# Install dependencies first (better layer caching: only reinstalls if requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Folder where jobs.db / jobs_results.json get written
RUN mkdir -p /app/data

CMD ["python", "main.py"]
