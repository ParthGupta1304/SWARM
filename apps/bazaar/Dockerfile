FROM python:3.11-slim

WORKDIR /app
COPY . ./
RUN pip install --no-cache-dir .[dev]
CMD ["uvicorn", "bazaar.main:app", "--host", "0.0.0.0", "--port", "8000"]
