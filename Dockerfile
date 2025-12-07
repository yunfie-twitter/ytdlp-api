FROM python:3.11-slim

# Install system dependencies including GPU support, aria2, and Deno
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    aria2 \
    unzip \
    # GPU encoding support
    intel-media-va-driver \
    i965-va-driver \
    vainfo \
    libva-drm2 \
    libva2 \
    mesa-va-drivers \
    && rm -rf /var/lib/apt/lists/*

# Install Deno
RUN curl -fsSL https://deno.land/install.sh | sh && \
    mv /root/.deno/bin/deno /usr/local/bin/deno && \
    chmod +x /usr/local/bin/deno

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create downloads directory
RUN mkdir -p /app/downloads

# Set environment for hardware acceleration
ENV LIBVA_DRIVER_NAME=iHD

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
