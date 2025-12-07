"""Root entry point for the yt-dlp Download API"""
from app.main import app

if __name__ == "__main__":
    import uvicorn
    from core.config import settings
    
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
