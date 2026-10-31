FROM python:3.11-slim
WORKDIR /app
# Build with the repository root as context; canonical contracts live at root.
COPY . ./
RUN pip install --no-cache-dir .[postgres,charts]
CMD ["uvicorn", "apps.bazaar.bazaar.main:app", "--host", "0.0.0.0", "--port", "8000"]
