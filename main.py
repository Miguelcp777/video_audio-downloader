from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import os
import tempfile
import urllib.parse
import asyncio
import json
import threading
import uuid
import time

app = FastAPI(title="Media Downloader Pro Engine")

# Permite que el index.html se conecte si es abierto desde un origen diferente (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def serve_index():
    return FileResponse("index.html")

# Estado de tareas en memoria (efímero — se resetea al reiniciar el contenedor)
tasks: dict = {}

def cleanup_old_tasks():
    cutoff = time.time() - 600  # Eliminar tareas con más de 10 minutos
    to_delete = [tid for tid, t in list(tasks.items()) if t.get('created_at', 0) < cutoff]
    for tid in to_delete:
        filepath = tasks[tid].get('filepath')
        if filepath:
            try:
                os.remove(filepath)
            except Exception:
                pass
        tasks.pop(tid, None)

class DownloadRequest(BaseModel):
    url: str
    format: str  # 'MP4' or 'MP3'
    quality: str = "MAX"  # 'MAX', 'MED', 'LOW'

def remove_file(path: str):
    try:
        os.remove(path)
    except Exception as e:
        print(f"Error borrando archivo temporal {path}: {e}")

def make_progress_hook(task_id: str):
    def hook(d):
        if d['status'] == 'downloading':
            pct_str = d.get('_percent_str', '0%').strip().replace('%', '')
            try:
                tasks[task_id]['progress'] = float(pct_str)
            except Exception:
                pass
            tasks[task_id]['download_status'] = 'downloading'
        elif d['status'] == 'finished':
            tasks[task_id]['download_status'] = 'processing'
            tasks[task_id]['progress'] = 99
    return hook

def _run_download(task_id: str, url: str, fmt: str, quality: str):
    try:
        temp_dir = tempfile.gettempdir()
        # Usamos task_id como nombre de archivo para evitar colisiones entre descargas simultáneas
        ydl_opts = {
            'outtmpl': os.path.join(temp_dir, f'{task_id}.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            },
            'progress_hooks': [make_progress_hook(task_id)],
        }

        if fmt == 'MP3':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            })
        else:
            if quality == "LOW":
                ydl_opts['format'] = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best'
            elif quality == "MED":
                ydl_opts['format'] = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best'
            else:
                ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

            if 'requested_downloads' in info_dict and len(info_dict['requested_downloads']) > 0:
                filename = info_dict['requested_downloads'][0]['filepath']
            else:
                filename = ydl.prepare_filename(info_dict)
                if fmt == 'MP3':
                    base, _ = os.path.splitext(filename)
                    filename = base + '.mp3'

            if not os.path.exists(filename):
                raise Exception("No se pudo localizar el archivo guardado en el servidor.")

            title = info_dict.get('title', 'Media')
            safe_title = "".join(x for x in title if x.isalnum() or x in " -_")
            display_name = f"{safe_title}.mp3" if fmt == 'MP3' else f"{safe_title}.mp4"

            tasks[task_id].update({
                'status': 'done',
                'filepath': filename,
                'display_name': display_name,
                'format': fmt,
                'progress': 100,
            })

    except yt_dlp.utils.ExtractorError as e:
        err_str = str(e).lower()
        if 'login' in err_str or 'sign in' in err_str or 'private' in err_str:
            msg = "Este contenido requiere inicio de sesión. Instagram y Facebook privados no están soportados."
        elif 'geo' in err_str or 'not available in your country' in err_str:
            msg = "Este contenido no está disponible en la región del servidor."
        else:
            msg = f"No se puede extraer el contenido. ({str(e)[:100]})"
        tasks[task_id].update({'status': 'error', 'error': msg})

    except yt_dlp.utils.DownloadError as e:
        err_str = str(e).lower()
        if '429' in err_str or 'too many requests' in err_str:
            msg = "Demasiadas solicitudes a esta plataforma. Espera unos minutos e intenta de nuevo."
        elif 'http error 403' in err_str:
            msg = "Acceso denegado por la plataforma (403). El contenido puede ser privado."
        elif 'http error 404' in err_str:
            msg = "El video no existe o fue eliminado (404)."
        else:
            msg = f"Error de descarga: {str(e)[:150]}"
        tasks[task_id].update({'status': 'error', 'error': msg})

    except Exception as e:
        tasks[task_id].update({'status': 'error', 'error': f"Error interno: {str(e)[:200]}"})


@app.post("/api/download")
async def download_media(req: DownloadRequest):
    cleanup_old_tasks()
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'status': 'starting',
        'download_status': 'starting',
        'progress': 0,
        'created_at': time.time(),
    }
    thread = threading.Thread(
        target=_run_download,
        args=(task_id, req.url, req.format, req.quality),
        daemon=True,
    )
    thread.start()
    return JSONResponse({'task_id': task_id})


@app.get("/api/progress/{task_id}")
async def stream_progress(task_id: str):
    async def event_generator():
        while True:
            task = tasks.get(task_id)
            if not task:
                yield f"data: {json.dumps({'status': 'error', 'error': 'Tarea no encontrada.'})}\n\n"
                break

            status = task.get('status', 'starting')
            dl_status = task.get('download_status', 'starting')
            progress = task.get('progress', 0)

            yield f"data: {json.dumps({'status': dl_status, 'progress': progress})}\n\n"

            if status == 'done':
                yield f"data: {json.dumps({'status': 'done', 'progress': 100, 'task_id': task_id})}\n\n"
                break
            elif status == 'error':
                yield f"data: {json.dumps({'status': 'error', 'error': task.get('error', 'Error desconocido.')})}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Necesario si hay nginx como reverse proxy (Synology DSM)
            "Connection": "keep-alive",
        },
    )


@app.get("/api/file/{task_id}")
async def get_file(task_id: str, background_tasks: BackgroundTasks):
    task = tasks.get(task_id)
    if not task or task.get('status') != 'done':
        raise HTTPException(status_code=404, detail="Archivo no disponible o tarea no completada.")

    filepath = task.get('filepath')
    display_name = task.get('display_name', 'media.mp4')
    fmt = task.get('format', 'MP4')

    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Archivo no encontrado en el servidor.")

    background_tasks.add_task(remove_file, filepath)
    tasks.pop(task_id, None)

    mime_type = 'audio/mpeg' if fmt == 'MP3' else 'video/mp4'
    # RFC 5987: soporte para nombres de archivo con caracteres no-ASCII (iOS Safari lo requiere)
    encoded_name = urllib.parse.quote(display_name)
    content_disposition = f"attachment; filename=\"{display_name}\"; filename*=UTF-8''{encoded_name}"

    return FileResponse(
        path=filepath,
        media_type=mime_type,
        headers={"Content-Disposition": content_disposition},
    )


@app.get("/api/info")
async def get_media_info(url: str):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 15,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            duration = info.get('duration')
            duration_str = None
            if duration:
                mins, secs = divmod(int(duration), 60)
                duration_str = f"{mins}:{secs:02d}"
            return JSONResponse({
                "title": info.get("title", "Sin título"),
                "thumbnail": info.get("thumbnail"),
                "duration": duration_str,
                "platform": info.get("extractor_key", "Desconocido"),
                "uploader": info.get("uploader"),
            })
    except yt_dlp.utils.ExtractorError as e:
        raise HTTPException(status_code=422, detail=f"No se puede acceder: {str(e)[:200]}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
