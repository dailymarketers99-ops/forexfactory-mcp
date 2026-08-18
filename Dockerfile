FROM python:3.12-slim

WORKDIR /app

# Install system deps needed for playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget gnupg ca-certificates \
    fonts-liberation libasound2 libatk1.0-0 libcups2 libdbus-1-3 \
    libdrm2 libgbm1 libgtk-3-0 libnspr4 libnss3 libx11-xcb1 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libxshmfence1 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy project
COPY . ./

# Install project deps (this installs the playwright package itself)
RUN uv pip install --system -e .

# Install Chromium browser binary (must come after project deps so versions match)
RUN playwright install --with-deps chromium

# Ensure src is on path
ENV PYTHONPATH=/app/src

# Run server
ENTRYPOINT ["uv", "run", "ffcal-server"]
