# Docker runtime for PulseFiles+. Before build, Pulse copies pulse_plugin into
# .pulse_plugin_sdk/ (classic builder). Local: clone SDK there, then docker build.
FROM python:3.12-slim
WORKDIR /plugin
COPY .pulse_plugin_sdk /tmp/pulse_plugin
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir /tmp/pulse_plugin \
    && pip install --no-cache-dir -r backend/requirements.txt
COPY . .
WORKDIR /plugin/backend
# Port comes from PULSE_PLUGIN_PORT; data — /plugin/data, Files folder — /plugin/files
ENV PULSE_PLUGIN_PORT=8080
CMD ["sh", "-c", "exec uvicorn files_plus.app:app --host 0.0.0.0 --port ${PULSE_PLUGIN_PORT}"]
