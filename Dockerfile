FROM python:3.12-slim

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY storygraph_box.py /app/storygraph_box.py
WORKDIR /app

CMD ["python", "/app/storygraph_box.py"]
