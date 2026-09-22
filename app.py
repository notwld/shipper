"""Vercel entrypoint — top-level Flask `app` required for detection."""
from application import create_app

app = create_app()

# Register Socket.IO handlers on the shared socketio instance
import realtime  # noqa: E402, F401
