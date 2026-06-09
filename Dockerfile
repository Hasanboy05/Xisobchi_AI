FROM python:3.11-slim

WORKDIR /app

# Tesseract va kerakli tizim paketlarini o'rnatish
# Bu qatlam kesh qilinadi — requirements o'zgarmasa qayta o'rnatilmaydi
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-uzb \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# requirements alohida nusxalanadi — faqat u o'zgarganda pip qayta ishlaydi
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Qolgan fayllar
COPY . .

CMD ["python", "main.py"]
