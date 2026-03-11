import uvicorn

from src.app.core.config import settings
from src.app.main import create_app

app = create_app(settings.TEST)

if __name__ == "__main__":
    uvicorn.run(
        "src.app.__main__:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
    )
