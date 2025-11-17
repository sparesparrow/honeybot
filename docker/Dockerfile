FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml setup.py ./
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create logs directory
RUN mkdir -p /app/logs

# Expose port
EXPOSE 8000

# Default command
CMD ["python", "-m", "scaipot.main"]
