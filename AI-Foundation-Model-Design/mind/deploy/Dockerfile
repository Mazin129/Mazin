# Vio — serving image (reasoner + retrieval + web). Build context is the mind/ folder.
FROM python:3.12-slim

WORKDIR /app
COPY deploy/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# app code (datasets, agents, web, everything in mind/)
COPY . /app

# bound to all interfaces INSIDE the container (Caddy is the only public door);
# the startup guard still refuses this without VIO_TOKEN, so security is enforced.
ENV MIND_HOST=0.0.0.0 \
    MIND_PORT=8100 \
    VIO_NO_BROWSER=1 \
    VIO_DATA_DIR=/data \
    VIO_HTTPS=1

VOLUME ["/data"]
EXPOSE 8100

# simple healthcheck against the login/app page
HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8100/',timeout=4)" || exit 1

CMD ["python", "web.py", "--service"]
