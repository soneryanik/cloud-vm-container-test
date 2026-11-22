# Same Python version (3.10) as the Ubuntu 22.04 VM, so only the
# virtualization layer differs between the two alternatives.
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

EXPOSE 8000
# 2 gunicorn workers, identical to the VM's systemd service.
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:8000", "app:app"]
