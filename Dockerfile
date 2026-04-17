# Usa una imagen oficial de Python ligera
FROM python:3.11-slim

# Instala FFmpeg a nivel sistema (vital para yt-dlp)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Establece el directorio de trabajo
WORKDIR /app

# Copia los requerimientos e instálalos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código fuente
COPY . .

# Expone el puerto (Render lo inyecta dinámicamente)
EXPOSE 8000

# Comando para ejecutar la app usando la variable de entorno $PORT (típico en nubes)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
