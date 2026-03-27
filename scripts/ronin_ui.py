import os
import requests
import json
import threading
import modules.scripts as scripts
import gradio as gr
from modules import paths, shared, script_callbacks

LORA_DIR = os.path.join(paths.models_path, "Lora")

def on_ui_settings():
    section = ('civitai_flow', "CivitaiFlow Manager")
    shared.opts.add_option("civitai_api_key", shared.OptionInfo("", "Civitai API Key (Ronin Edition)", gr.Textbox, {"visible": True}, section=section))
script_callbacks.on_ui_settings(on_ui_settings)

def fetch_data(query, limit, page):
    api_key = shared.opts.data.get("civitai_api_key", "")
    if not api_key: return [], "❌ Falla: Sin API Key en Settings", [], page
    if not query: return [], "⚠️ Ingresa un tag", [], page

    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
    api_url = f"https://civitai.com/api/v1/models?query={query.replace(' ', '+')}&limit={int(limit)}&page={int(page)}&types=LORA&sort=Highest+Rated"
    
    try:
        res = requests.get(api_url, headers=headers, timeout=15)
        models = res.json().get('items', [])
        
        if not models:
            return [], "❌ Fin de los resultados.", [], page

        gallery_images = []
        for m in models:
            name = m['name']
            img_url = "https://placehold.co/400x600?text=No+Image"
            if m.get('modelVersions') and m['modelVersions'][0].get('images'):
                img_url = m['modelVersions'][0]['images'][0]['url']
            gallery_images.append((img_url, name))
            
        return gallery_images, f"✅ Pág {page}. Haz CLIC en cualquier foto para descargar al instante.", models, page
    except Exception as e:
        return [], f"❌ Error: {str(e)}", [], page

def change_page(query, limit, current_page, direction):
    new_page = max(1, current_page + direction)
    return fetch_data(query, limit, new_page)

# --- CORE DOWNLODER (Corre en Background) ---
def download_single_item(model_data, api_key):
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
    version = model_data['modelVersions'][0]
    
    clean_name = "".join([c for c in model_data['name'] if c.isalnum() or c in (' ', '_')]).rstrip()
    category = model_data['tags'][0].replace(' ', '_').replace('/', '_') if model_data.get('tags') else "General"
    
    target_dir = os.path.join(LORA_DIR, category)
    os.makedirs(target_dir, exist_ok=True)
    
    base_path = os.path.join(target_dir, clean_name)
    safetensors_path = f"{base_path}.safetensors"
    info_path = f"{base_path}.civitai.info" # Para el Activation Text
    preview_path = f"{base_path}.preview.png"

    if os.path.exists(safetensors_path):
        print(f"[CivitaiFlow] SKIP: {clean_name} ya existe.")
        return

    try:
        # Metadatos para Forge
        v_url = f"https://civitai.com/api/v1/model-versions/{version['id']}"
        v_info = requests.get(v_url, headers=headers, timeout=10).json()
        with open(info_path, 'w', encoding='utf-8') as f: json.dump(v_info, f, indent=4)
        
        # Preview
        if version.get('images'):
            img_r = requests.get(version['images'][0]['url'], timeout=10)
            with open(preview_path, 'wb') as f: f.write(img_r.content)

        # Safetensors
        dl_url = f"https://civitai.com/api/download/models/{version['id']}"
        r = requests.get(dl_url + f"?token={api_key}", stream=True, timeout=600)
        
        if r.status_code == 200:
            with open(safetensors_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk)
            print(f"[CivitaiFlow] EXITOSO: Descargado {clean_name}")
        else:
            print(f"[CivitaiFlow] ERROR {r.status_code}: {clean_name}")
    except Exception as e:
        print(f"[CivitaiFlow] ERROR CRÍTICO en {clean_name}: {str(e)}")

# --- EL GATILLO (INSTANT TRIGGER) ---
def instant_download(evt: gr.SelectData, hidden_data):
    api_key = shared.opts.data.get("civitai_api_key", "")
    if not api_key: return "❌ Error: Sin API Key"
    
    selected_model = hidden_data[evt.index]
    name = selected_model['name']
    
    # Dispara el hilo en segundo plano (SysAdmin Magic)
    threading.Thread(target=download_single_item, args=(selected_model, api_key), daemon=True).start()
    
    return f"🚀 Descarga iniciada en segundo plano: {name}"

# --- UI TABS ---
def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False) as civitai_flow_tab:
        hidden_data = gr.State([])
        current_page = gr.State(1)

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 1. Búsqueda y Navegación")
                search_query = gr.Textbox(label="Tag", placeholder="ej: Ahri")
                limit_slider = gr.Slider(minimum=10, maximum=50, step=10, label="Resultados por página", value=20)
                search_btn = gr.Button("🔍 Buscar", variant="secondary")
                
                with gr.Row():
                    prev_btn = gr.Button("⬅️ Página Anterior")
                    next_btn = gr.Button("Página Siguiente ➡️")
                
                gr.Markdown("---")
                gr.Markdown("### 2. Log de Acción")
                status_log = gr.Textbox(label="Status de Gatillo", lines=3)

            with gr.Column(scale=3):
                gr.Markdown("### Catálogo (Haz CLIC en una foto para descargar al instante)")
                gallery = gr.Gallery(label="Catálogo", show_label=False, columns=[4], object_fit="contain", height="auto", allow_preview=False)

        # Eventos Búsqueda
        search_btn.click(fn=lambda q, l: fetch_data(q, l, 1), inputs=[search_query, limit_slider], outputs=[gallery, status_log, hidden_data, current_page])
        search_query.submit(fn=lambda q, l: fetch_data(q, l, 1), inputs=[search_query, limit_slider], outputs=[gallery, status_log, hidden_data, current_page])
        
        # Eventos Paginación
        prev_btn.click(fn=change_page, inputs=[search_query, limit_slider, current_page, gr.State(-1)], outputs=[gallery, status_log, hidden_data, current_page])
        next_btn.click(fn=change_page, inputs=[search_query, limit_slider, current_page, gr.State(1)], outputs=[gallery, status_log, hidden_data, current_page])
        
        # EL EVENTO MÁGICO: Clic en la foto = Descarga inmediata
        gallery.select(fn=instant_download, inputs=[hidden_data], outputs=status_log)
        
    return [(civitai_flow_tab, "CivitaiFlow", "civitai_flow_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)
