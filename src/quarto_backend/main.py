import logging

import socketio  # type: ignore[reportMissingModuleSource]

from .api.app import app
from .socket.handler import sio

logging.basicConfig(level=logging.INFO)

app = socketio.ASGIApp(sio, app)
