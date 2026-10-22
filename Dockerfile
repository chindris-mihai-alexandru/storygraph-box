FROM python:3.12-slim

RUN pip install --no-cache-dir "audible[cryptography]" PyGithub

COPY storygraph_box.py /app/storygraph_box.py
WORKDIR /app

CMD ["python", "/app/storygraph_box.py"]