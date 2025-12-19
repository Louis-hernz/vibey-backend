FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for SQLite database
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Environment variables
ENV DATABASE_URL=sqlite:////app/data/vibey.db
ENV PYTHONUNBUFFERED=1

# Initialize database on startup and run server
CMD ["sh", "-c", "python database.py && uvicorn main:app --host 0.0.0.0 --port 8000"]
