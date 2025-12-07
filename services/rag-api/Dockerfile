FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (MeCab, build tools)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    mecab \
    libmecab-dev \
    mecab-ipadic-utf8 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install heavy python dependencies first for caching
RUN pip install --no-cache-dir \
    torch>=2.0.0 \
    sentence-transformers>=2.2.2 \
    faiss-cpu>=1.7.4 \
    numpy>=1.24.0 \
    pandas>=2.0.0

# Copy rag-core package
COPY packages/rag-core /packages/rag-core

# Install rag-core
RUN pip install -e /packages/rag-core

# Copy requirements and install
COPY services/rag-api/requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY services/rag-api/src ./src

# Create directory for indices
RUN mkdir -p indices

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python", "-m", "src.main"]

