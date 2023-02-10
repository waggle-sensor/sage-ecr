FROM python:3.11
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
CMD gunicorn ecr_api:app --log-level=info --bind=0.0.0.0:5000 --reload --graceful-timeout 630 --timeout 700
