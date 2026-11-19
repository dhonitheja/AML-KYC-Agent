FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
COPY watchlists/sample.xml ./watchlists/sample.xml
COPY tests ./tests
ENTRYPOINT ["python", "-u", "pipeline.py"]
