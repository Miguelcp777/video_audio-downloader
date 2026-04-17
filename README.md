# Media Downloader Pro 🎥🎵

A fast, server-side media downloading tool built with **FastAPI**, **yt-dlp**, and a sleek **Google Material Dark Mode** frontend. It enables you to download videos and audio (MP3) in maximum quality directly to your device (Mobile or Desktop) from almost any social network (YouTube, X, Instagram, TikTok, Facebook).

## 🚀 Features
- **Cross-Platform Extraction:** Seamlessly bypasses limitations using `yt-dlp` in the background.
- **HQ Audio Conversion:** Automatic extraction to pristine 320kbps MP3 (Requires `FFmpeg`).
- **Responsive UI:** Dark Mode aesthetic interface explicitly designed to trigger your browser's native Save Dialog.
- **Cloud Ready:** Engineered exclusively to be deployed effortlessly on container platforms.

## 📦 Tech Stack
- Frontend: `Vanilla HTML/JS`, `TailwindCSS`
- Backend: `Python`, `FastAPI`, `Uvicorn`
- Engines: `yt-dlp`, `FFmpeg`

## ☁️ Deployment (Railway or Render)
This application includes the proper configurations (`Dockerfile` and `apt.txt`) to run instantly in the Cloud without manual adjustments. 

**Railway 1-Click Method:**
1. Connect this GitHub Repository.
2. Railway will automatically detect the Dockerfile/Nixpack.
3. Once built, open the provided Public URL from any mobile phone or browser to start downloading remotely.

## 💻 Local Setup
To test or run locally in your own machine:
1. Ensure **Python > 3.10** and **FFmpeg** are installed and mapped to your system `PATH`.
2. Install pip dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the development server specifying your local IP if testing from mobile:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
4. Access via `http://localhost:8000` or `http://<your-ip>:8000` from your mobile phone.

---
*Created as a unified downloading solution bypassing local browser limitations.*
