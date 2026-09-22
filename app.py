"""Vercel entrypoint — top-level Flask `app` required for detection."""
from application import create_app

app = create_app()

# Register Socket.IO event handlers onto the shared socketio instance
import main  # noqa: E402, F401
