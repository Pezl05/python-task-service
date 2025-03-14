FROM python:3.13.1-alpine

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
RUN opentelemetry-bootstrap --action=install

COPY ./app /code/app

CMD ["opentelemetry-instrument", "uvicorn", "main:app", "--app-dir", "app/", "--host", "0.0.0.0", "--port", "3000"]