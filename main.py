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
    quality: str = "MAX" # 'MAX', 'MED', 'LOW'

def remove_file(path: str):
    try:
        os.remove(path)
    except Exception as e:
        print(f"Error borrando archivo temporal {path}: {e}")

@app.post("/api/download")
async def download_media(req: DownloadRequest, background_tasks: BackgroundTasks):
    try:
        temp_dir = tempfile.gettempdir()
        
        # Usamos %(id)s en lugar de %(title)s para evitar errores de caracteres especiales en Linux/NAS
        ydl_opts = {
            'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
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
            if req.quality == "LOW":
                ydl_opts['format'] = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best'
            elif req.quality == "MED":
                ydl_opts['format'] = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best'
            else:
                ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(req.url, download=True)
            
            # Obtener el archivo final procesado para asegurar que encontramos el mp3 o mp4
            if 'requested_downloads' in info_dict and len(info_dict['requested_downloads']) > 0:
                filename = info_dict['requested_downloads'][0]['filepath']
            else:
                filename = ydl.prepare_filename(info_dict)
                if req.format == 'MP3':
                    base, _ = os.path.splitext(filename)
                    filename = base + '.mp3'
                
            if not os.path.exists(filename):
                raise Exception(f"No se pudo localizar el archivo guardado en el servidor.")
            
            background_tasks.add_task(remove_file, filename)
            
            # Limpiar nombre bonito para el navegador del usuario 
            title = info_dict.get('title', 'Media')
            # Evitar comillas u otros chars raros en el header
            safe_title = "".join(x for x in title if x.isalnum() or x in " -_")
            display_name = f"{safe_title}.mp3" if req.format == 'MP3' else f"{safe_title}.mp4"
            
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
