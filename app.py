import os
import sys
from pathlib import Path

# Add wardrobe to python path
sys.path.insert(0, str(Path(__file__).parent / "wardrobe"))

import gradio as gr
from backend.main import app as fastapi_app

with gr.Blocks(title="Wardrobe Cutout & Flat-Lay API") as demo:
    gr.Markdown("# 👗 OOTD Wardrobe Cutout & Flat-Lay Service")
    gr.Markdown("FastAPI backend is running and connected to Lovable!")
    gr.Markdown("### Endpoints Available:")
    gr.Markdown("- **Health Check:** `GET /healthz`")
    gr.Markdown("- **Cutout & Flat-Lay:** `POST /api/cutout`")

# Mount existing FastAPI app so all /api/... routes work seamlessly
app = gr.mount_gradio_app(fastapi_app, demo, path="/")
