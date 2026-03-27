import os
import requests
import modules.scripts as scripts
import gradio as gr
from modules import paths, shared

LORA_DIR = os.path.join(paths.models_path, "Lora")

def download_civitai(api_key, query, limit):
    if not api_key: return "Error: Falta el API Key"
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
    api_url = f"https://civitai.com/api/v1/models?query={query.replace(' ', '+')}&limit={int(limit)}&types=LORA&sort=Highest+Rated"
    
    try:
        response = requests.get(api_url, headers=headers)
        models = response.json().get('items', [])
        if not models: return "No se encontraron modelos."

        count = 0
        for model in models:
            v = model['modelVersions'][0]
            name = "".join([c for c in model['name'] if c.isalnum() or c in (' ', '_')]).rstrip()
            cat = model['tags'][0] if model.get('tags') else "General"
            target = os.path.join(LORA_DIR, cat)
            os.makedirs(target, exist_ok=True)
            
            f_path = os.path.join(target, f"{name}.safetensors")
            if os.path.exists(f_path): continue
            
            r = requests.get(v['downloadUrl'] + f"?token={api_key}", stream=True)
            with open(f_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            count += 1
        return f"Exito: {count} modelos en {LORA_DIR}"
    except Exception as e: return f"Error: {str(e)}"

class Script(scripts.Script):
    def title(self): return "Ronin Civitai Manager"
    def show(self, is_img2img): return scripts.AlwaysVisible
    def ui(self, is_img2img):
        with gr.Accordion("Ronin Civitai Collector", open=False):
            key = gr.Textbox(label="API Key", value="82ea1e2262e6cf5413d6f55e5a8b761d")
            q = gr.Textbox(label="Tag", placeholder="ej: Zenless Zone Zero")
            lim = gr.Slider(minimum=1, maximum=100, value=20, label="Limite")
            btn = gr.Button("Descargar", variant="primary")
            out = gr.Textbox(label="Log")
            btn.click(fn=download_civitai, inputs=[key, q, lim], outputs=[out])
        return [key, q, lim]
