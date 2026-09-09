FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
# CRITICAL: presidio-analyzer depends on en-core-web-lg (~400 MB).
# We install everything else, then presidio with --no-deps.
RUN pip install --no-cache-dir --upgrade pip && \
    python -c "with open('requirements.txt') as f: open('/tmp/req2.txt','w').write(''.join(l for l in f if not l.strip().startswith('presidio')))" && \
    pip install --no-cache-dir -r /tmp/req2.txt && \
    pip install --no-cache-dir spacy && \
    python -m spacy download en_core_web_sm && \
    pip install --no-cache-dir --no-deps presidio-analyzer presidio-anonymizer && \
    python -c "import spacy; nlp=spacy.load('en_core_web_sm'); print('OK: small model loaded, vocab size:', len(nlp.vocab))"

# Copy application
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run FastAPI
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
