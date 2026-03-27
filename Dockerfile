FROM python:3.12-slim

WORKDIR /app

# Install curl for downloading rules file
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Download comprehensive rules and seed the database at build time
RUN mkdir -p data && \
    curl -L -o data/comprehensive_rules.txt "https://media.wizards.com/2025/downloads/MagicCompRules%2020250207.txt" && \
    python scripts/seed_rules.py

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
