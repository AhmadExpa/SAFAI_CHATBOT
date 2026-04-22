# Use a Python version compatible with current dependencies and type syntax
FROM python:3.11-slim

# Set environment variables
# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE 1
# Ensure Python output is sent straight to terminal (useful for logging)
ENV PYTHONUNBUFFERED 1
# Default port
ENV PORT 8000

# Set work directory
WORKDIR /app

# Install system dependencies
# gcc and libpq-dev are often needed for postgres and other C-based extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
# Using gunicorn with uvicorn workers as per the Procfile configuration
# The ${PORT} variable allows Coolify/Railway to inject the port
CMD ["sh", "-c", "gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:${PORT}"]
