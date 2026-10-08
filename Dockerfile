FROM python:3.12-slim
WORKDIR /plugin
COPY backend/requirements.txt /plugin/requirements.txt
RUN pip install --no-cache-dir -r /plugin/requirements.txt \
    && pip install --no-cache-dir "pulse-plugin @ git+https://github.com/pulse-assist/pulse-plugin-sdk@v1.1.0" \
    || pip install --no-cache-dir fastapi uvicorn httpx pymongo PyJWT
COPY . /plugin
ENV PYTHONPATH=/plugin/backend
# Port comes from PULSE_PLUGIN_PORT (supervisor); default 8080 for local runs.
ENV PULSE_PLUGIN_PORT=8080
CMD uvicorn files_plus.app:app --host 0.0.0.0 --port ${PULSE_PLUGIN_PORT}
