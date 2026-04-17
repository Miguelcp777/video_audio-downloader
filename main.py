from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import yt_dlp
import os
import tempfile
from pathlib import Path

app = FastAPI(title="Media Downloader Pro Engine")

# Permite que el index.html se conecte si es abierto desde un origen diferente (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servimos de forma estática la carpeta actual para assets/fotos si las hubiera
# app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
def serve_index():
    # Devuelve el index.html principal para el Frontend
    return FileResponse("index.html")

class DownloadRequest(BaseModel):
    url: str
    format: str # 'MP4' or 'MP3'

def remove_file(path: str):
    try:
        os.remove(path)
    except Exception as e:
        print(f"Error borrando archivo temporal {path}: {e}")

@app.post("/api/download")
async def download_media(req: DownloadRequest, background_tasks: BackgroundTasks):
    try:
        # Usamos un directorio temporal del sistema operativo
        temp_dir = tempfile.gettempdir()
        
        ydl_opts = {
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
        }
        
        if req.format == 'MP3':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            })
        else:
            # Video = MP4 standard best quality
            ydl_opts.update({
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            })
            
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Primero extraemos la info para saber el nombre de archivo exacto
            info_dict = ydl.extract_info(req.url, download=True)
            # El archivo final después de los postprocessors se obtiene así:
            filename = ydl.prepare_filename(info_dict)
            
            # En caso de MP3, prepare_filename retorna .webm o .m4a y postprocessor cambia a .mp3
            if req.format == 'MP3':
                # Reemplazamos la extension
                base, _ = os.path.splitext(filename)
                filename = base + '.mp3'
                
            if not os.path.exists(filename):
                raise Exception("El archivo no se pudo encontrar tras la descarga.")
            
            # Devolvemos el archivo mediante FileResponse
            # Agregamos una tarea en background para borrar el archivo temporal luego de descargarlo
            background_tasks.add_task(remove_file, filename)
            
            # Extraemos el nombre original para usarlo como descarga. Omitimos la ruta completa del server.
            display_name = os.path.basename(filename)
            
            return FileResponse(
                path=filename, 
                filename=display_name, 
                media_type='application/octet-stream'
            )
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
