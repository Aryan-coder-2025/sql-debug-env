FROM python:3.12

# Hugging Face Spaces requires running as a non-root user (UID 1000)
RUN useradd -m -u 1000 user

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create dynamic output directories and grant ownership to the HF user
RUN mkdir -p outputs/trajectories outputs/logs databases && \
    chown -R user:user /app && \
    chmod -R 777 /app

# Switch to the non-root user for runtime
USER user

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:7860/health'); r.raise_for_status()" || exit 1

CMD ["python", "main.py"]
