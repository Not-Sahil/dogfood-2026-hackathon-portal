FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:///./data/dogfood.db
ENV AUTO_CREATE_DB=true
ENV SEED_ON_START=true
ENV FIXTURES_PATH=/app/fixtures.json

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
