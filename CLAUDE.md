# CLAUDE.md — Media Downloader Pro

## Arquitectura

| Componente | Archivo | Descripción |
|-----------|---------|-------------|
| Backend   | `main.py` | FastAPI, ~200 líneas |
| Frontend  | `index.html` | SPA de un solo archivo, Vanilla JS + Tailwind CDN |
| Motor     | yt-dlp + FFmpeg | Extracción de media y conversión de audio |
| Deploy    | Docker en Synology NAS | Container Manager / docker-compose |

## Restricciones Importantes

- **NO** añadir nuevas dependencias Python sin actualizar `requirements.txt` y el `Dockerfile`
- **NO** usar frameworks JS en el frontend — solo Vanilla JS
- **NO** añadir base de datos — el estado de tareas en memoria es aceptable (efímero por diseño)
- Mantener la arquitectura de un único archivo para `main.py` y `index.html`

## Flujo de Descarga (SSE)

```
POST /api/download  →  { task_id }  →  thread lanza _run_download()
GET  /api/progress/{task_id}  →  SSE stream con % real de yt-dlp
GET  /api/file/{task_id}      →  FileResponse con el archivo cuando status='done'
```

## iOS / Android — Conocimiento Crítico

- **iOS Safari ignora `<a download>`** — el archivo se abre inline en vez de guardarse
- **Solución**: usar `navigator.share({ files: [file] })` (Web Share API Level 2, iOS 14+)
- El `navigator.share()` **debe** llamarse directamente desde un handler de click de usuario (sin `await` antes). Por eso en iOS se muestra un botón "Guardar Archivo" en vez de activarse automáticamente
- **Detección iOS**: `( /iPhone|iPad|iPod/i.test(navigator.userAgent) ) || ( navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1 )` — el segundo caso cubre iPadOS 13+ que reporta MacIntel
- **Android / Desktop**: blob URL + `<a download>` funciona correctamente

## MIME Types y Content-Disposition

- Backend **debe** enviar `video/mp4` o `audio/mpeg`, **nunca** `application/octet-stream`
- Content-Disposition debe incluir `filename*=UTF-8''<encoded>` (RFC 5987) para nombres con caracteres no-ASCII
- No usar el parámetro `filename=` de `FileResponse` junto con `headers={"Content-Disposition": ...}` — genera header duplicado

## SSE en Synology

- Si hay nginx como reverse proxy (DSM Web Station), el header `X-Accel-Buffering: no` es obligatorio en los responses SSE para evitar buffering
- La app corre en Synology NAS — no hay timeout de 30s de cloud providers, las descargas largas de YouTube funcionan sin cortar

## yt-dlp

- Usar `requested_downloads[0]['filepath']` para obtener la ruta del archivo final (post-postprocessors)
- MP3: la conversión via FFmpegExtractAudio cambia la extensión — no confiar en `prepare_filename()`
- `socket_timeout: 30` en `ydl_opts` para evitar cuelgues
- Capturar `yt_dlp.utils.ExtractorError` antes que `yt_dlp.utils.DownloadError` (más específico primero)
- Instagram/Facebook/TikTok pueden fallar sin cookies — mapear a mensajes de error en español

## Cookies (Contenido Privado)

- El `docker-compose.yml` tiene un volumen `./cookies:/app/cookies:ro` (comentado por defecto)
- Para habilitar: crear `cookies/cookies.txt` en formato Netscape y añadir a `ydl_opts`: `'cookiefile': '/app/cookies/cookies.txt'`

## Manejo de Errores

- Capturar en orden: `ExtractorError` → `DownloadError` → `Exception` genérico
- Todos los mensajes de error al usuario deben estar en **español**
- Nunca exponer stack traces de yt-dlp al cliente — truncar a 200 chars
- Codigos HTTP: 422 para errores de extractor, 400 para errores de descarga, 500 para errores internos

## Ciclo de Vida de Archivos Temporales

- Descargas van a `tempfile.gettempdir()` con nombre `{task_id}.{ext}`
- `BackgroundTasks.add_task(remove_file, filepath)` limpia el archivo después del `FileResponse`
- `cleanup_old_tasks()` elimina tareas (y sus archivos) con más de 10 minutos al inicio de cada nueva descarga

## Variables de Entorno

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `PORT`   | `8000`            | Puerto del servidor uvicorn |
| `TZ`     | `Europe/Madrid`   | Zona horaria para logs correctos |

## Proceso de Despliegue en Synology

La app corre en un contenedor Docker en el Synology NAS en `/volume1/docker/video_audio_downloader`.
URL pública: `https://downloader.i-automate.es`

### Pasos para actualizar la app

**1. Copiar archivos al NAS** (desde Windows Explorer):
```
\\192.168.1.35\docker\video_audio_downloader
```
Copiar `main.py` e `index.html` sobreescribiendo los existentes.

**2. SSH al Synology y reconstruir:**
```bash
ssh admin@192.168.1.35
sudo docker-compose down && sudo docker-compose up --build -d
```

### Notas importantes del entorno
- Usar `docker-compose` (con guión, V1) — `docker compose` (V2) **no existe** en este Synology
- Siempre usar `sudo` — el usuario `admin` no tiene permisos directos al socket de Docker
- El Step 6 del build (`COPY . .`) no debe usar caché — confirma que el hash cambia entre builds
- Si el navegador muestra la versión vieja tras el rebuild, es caché de Cloudflare → hard refresh (`Ctrl+Shift+R`)
- Para verificar que la versión nueva está activa: `https://downloader.i-automate.es/api/info?url=https://youtu.be/dQw4w9WgXcQ` debe responder JSON con título y miniatura
