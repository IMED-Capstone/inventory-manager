# Adapted from: https://www.docker.com/blog/how-to-dockerize-django-app/

# Stage 1: Base build stage for app dependencies
FROM python:3.13-slim AS builder

RUN mkdir /app

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1 

RUN pip install --upgrade pip 

COPY requirements.txt /app/

RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Docs build stage
FROM python:3.13-slim AS docs-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    make \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Verify sphinx-build is available
RUN which sphinx-build || { echo "sphinx-build not found"; exit 1; }

RUN mkdir /app

WORKDIR /app

# Copy the Django project, core app, and docs source directories
COPY InventoryManager ./InventoryManager
COPY core ./core
COPY docs ./docs

# Set DJANGO_SETTINGS_MODULE for Sphinx
ENV DJANGO_SETTINGS_MODULE=InventoryManager.settings

# Build the Sphinx HTML documentation
RUN cd docs && make html

# Stage 3: Production stage
FROM python:3.13-slim

# if curl is needed for debugging intracontainer vs extracontainer networking quirks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN useradd -m -r appuser && \
    mkdir /app && \
    chown -R appuser /app

# Copy the Python dependencies from the app builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy the built Sphinx docs from the docs-builder stage
COPY --from=docs-builder --chown=appuser:appuser /app/docs/_build /app/docs/_build

WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . .

COPY --chown=appuser:appuser entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1 

# Switch to non-root user
USER appuser

EXPOSE 8000 8010

ENTRYPOINT ["/app/entrypoint.sh"]
