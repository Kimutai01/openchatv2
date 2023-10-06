FROM python:3.10

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV PORT 8001

WORKDIR /app

COPY . .

RUN pip install -r dev-requirements.txt


RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
 && rm -rf /var/lib/apt/lists/*
 
RUN python manage.py collectstatic --noinput
RUN python manage.py makemigrations --noinput || true
RUN python manage.py migrate --noinput || true

CMD python manage.py runserver 0.0.0.0:$PORT
