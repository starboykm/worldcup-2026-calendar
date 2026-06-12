FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN python -m worldcup_calendar update || true

EXPOSE 8080
CMD ["python", "-m", "worldcup_calendar", "serve", "--host", "0.0.0.0", "--port", "8080"]
