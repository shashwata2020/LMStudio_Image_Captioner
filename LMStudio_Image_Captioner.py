import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import os
import sys
import threading
import json
import base64
import re
import requests

# --- CONSTANTS ---
if getattr(sys, 'frozen', False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(_APP_DIR, "caption_config.json")
LMSTUDIO_DEFAULT_URL = "http://localhost:1234/v1"
SUPPORTED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp')

# --- THEMES ---
THEME_DARK = {
    "bg": "#1e1e1e",
    "fg": "#d4d4d4",
    "entry_bg": "#2d2d2d",
    "entry_fg": "#d4d4d4",
    "text_bg": "#2d2d2d",
    "text_fg": "#d4d4d4",
    "log_bg": "#1a1a1a",
    "log_fg": "#cccccc",
    "btn_bg": "#3c3c3c",
    "btn_fg": "#d4d4d4",
    "insert_bg": "#d4d4d4",
}

THEME_LIGHT = {
    "bg": "#f0f0f0",
    "fg": "#000000",
    "entry_bg": "#ffffff",
    "entry_fg": "#000000",
    "text_bg": "#ffffff",
    "text_fg": "#000000",
    "log_bg": "#f0f0f0",
    "log_fg": "#000000",
    "btn_bg": "#e0e0e0",
    "btn_fg": "#000000",
    "insert_bg": "#000000",
}


class CaptionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LM Studio Image Captioner")
        self.root.geometry("600x800")

        # --- UI LAYOUT ---
        main_frame = tk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.main_frame = main_frame

        # 0. THEME BUTTONS
        theme_frame = tk.Frame(main_frame)
        theme_frame.pack(fill=tk.X, pady=(0, 10))

        self.btn_dark = tk.Button(theme_frame, text="Dark Mode", command=lambda: self.switch_theme("dark"))
        self.btn_dark.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_light = tk.Button(theme_frame, text="Light Mode", command=lambda: self.switch_theme("light"))
        self.btn_light.pack(side=tk.LEFT)

        self.theme_frame = theme_frame

        # 1. LM STUDIO SERVER URL
        lbl_url = tk.Label(main_frame, text="LM Studio Server URL", font=("Arial", 10, "bold"), anchor="w")
        lbl_url.pack(fill=tk.X, pady=(0, 2))

        self.entry_url = tk.Entry(main_frame, font=("Consolas", 9))
        self.entry_url.pack(fill=tk.X, pady=5)

        # 2. FOLDER PATH
        lbl_path = tk.Label(main_frame, text="Path to Folder Containing Images", font=("Arial", 10, "bold"), anchor="w")
        lbl_path.pack(fill=tk.X, pady=(10, 2))

        path_frame = tk.Frame(main_frame)
        path_frame.pack(fill=tk.X, pady=5)

        self.entry_path = tk.Entry(path_frame)
        self.entry_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        btn_browse = tk.Button(path_frame, text="Browse", command=self.browse_folder)
        btn_browse.pack(side=tk.RIGHT)

        # 3. SYSTEM PROMPT
        lbl_sys_instr = tk.Label(main_frame, text="System Prompt", font=("Arial", 10, "bold"), anchor="w")
        lbl_sys_instr.pack(fill=tk.X, pady=(10, 2))

        self.txt_sys_instruction = scrolledtext.ScrolledText(main_frame, height=4, font=("Arial", 9))
        self.txt_sys_instruction.pack(fill=tk.X, pady=5)

        sys_btn_frame = tk.Frame(main_frame)
        sys_btn_frame.pack(fill=tk.X)

        btn_clear_sys = tk.Button(sys_btn_frame, text="Clear", command=lambda: self.txt_sys_instruction.delete('1.0', tk.END))
        btn_clear_sys.pack(side=tk.RIGHT, padx=(5, 0))

        btn_save_sys = tk.Button(sys_btn_frame, text="Save", command=self.save_prompts)
        btn_save_sys.pack(side=tk.RIGHT)

        # 4. USER PROMPT
        lbl_prompt = tk.Label(main_frame, text="User Prompt", font=("Arial", 10, "bold"), anchor="w")
        lbl_prompt.pack(fill=tk.X, pady=(10, 2))

        self.txt_prompt = scrolledtext.ScrolledText(main_frame, height=5, font=("Arial", 9))
        self.txt_prompt.pack(fill=tk.X, pady=5)

        prompt_btn_frame = tk.Frame(main_frame)
        prompt_btn_frame.pack(fill=tk.X)

        btn_clear_prompt = tk.Button(prompt_btn_frame, text="Clear", command=lambda: self.txt_prompt.delete('1.0', tk.END))
        btn_clear_prompt.pack(side=tk.RIGHT, padx=(5, 0))

        btn_save_prompt = tk.Button(prompt_btn_frame, text="Save", command=self.save_prompts)
        btn_save_prompt.pack(side=tk.RIGHT)

        # 5. START / STOP BUTTONS
        self.btn_start = tk.Button(
            main_frame, text="Start Captioning", bg="#4CAF50", fg="white",
            font=("Arial", 12, "bold"), command=self.start_thread
        )
        self.btn_start.pack(fill=tk.X, pady=(15, 5))

        self.btn_stop = tk.Button(
            main_frame, text="Stop Captioning", bg="#e53935", fg="white",
            disabledforeground="white",
            font=("Arial", 12, "bold"), command=self.stop_processing, state='disabled'
        )
        self.btn_stop.pack(fill=tk.X, pady=(0, 15))

        # 6. LOG
        log_header = tk.Frame(main_frame)
        log_header.pack(fill=tk.X, pady=(0, 2))

        lbl_log = tk.Label(log_header, text="Log", font=("Arial", 10, "bold"), anchor="w")
        lbl_log.pack(side=tk.LEFT)

        btn_clear_log = tk.Button(log_header, text="Clear Log", command=self.clear_log)
        btn_clear_log.pack(side=tk.RIGHT)

        self.txt_log = scrolledtext.ScrolledText(main_frame, height=10, state='disabled', bg="#f0f0f0", font=("Consolas", 8))
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        # State
        self.is_running = False
        self.current_theme = "light"

        # Track all themed widgets
        self.labels = [lbl_url, lbl_path, lbl_sys_instr, lbl_prompt, lbl_log]
        self.entries = [self.entry_url, self.entry_path]
        self.text_widgets = [self.txt_sys_instruction, self.txt_prompt]
        self.buttons = [btn_browse, btn_clear_sys, btn_save_sys, btn_clear_prompt, btn_save_prompt, btn_clear_log, self.btn_dark, self.btn_light]
        self.frames = [main_frame, path_frame, sys_btn_frame, prompt_btn_frame, theme_frame, log_header]

        # --- LOAD CONFIG ON STARTUP ---
        self.load_config()

    def browse_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.entry_path.delete(0, tk.END)
            self.entry_path.insert(0, folder_selected)

    def log(self, message):
        """Thread-safe logging."""
        def _update():
            self.txt_log.config(state='normal')
            self.txt_log.insert(tk.END, message + "\n")
            self.txt_log.see(tk.END)
            self.txt_log.config(state='disabled')
        self.root.after(0, _update)

    def clear_log(self):
        self.txt_log.config(state='normal')
        self.txt_log.delete('1.0', tk.END)
        self.txt_log.config(state='disabled')

    # --- THEME ---
    def switch_theme(self, theme_name):
        self.current_theme = theme_name
        self.apply_theme()
        # Persist theme choice
        self._save_theme_to_config(theme_name)

    def apply_theme(self):
        t = THEME_DARK if self.current_theme == "dark" else THEME_LIGHT

        self.root.config(bg=t["bg"])

        for frame in self.frames:
            frame.config(bg=t["bg"])

        for lbl in self.labels:
            lbl.config(bg=t["bg"], fg=t["fg"])

        for entry in self.entries:
            entry.config(bg=t["entry_bg"], fg=t["entry_fg"], insertbackground=t["insert_bg"])

        for txt in self.text_widgets:
            txt.config(bg=t["text_bg"], fg=t["text_fg"], insertbackground=t["insert_bg"])

        self.txt_log.config(bg=t["log_bg"], fg=t["log_fg"])

        for btn in self.buttons:
            btn.config(bg=t["btn_bg"], fg=t["btn_fg"], activebackground=t["entry_bg"], activeforeground=t["fg"])

    def _save_theme_to_config(self, theme_name):
        """Read existing config, update theme, write back."""
        data = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                pass
        data["theme"] = theme_name
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass

    # --- CONFIGURATION HANDLERS ---
    def load_config(self):
        """Loads settings from JSON file or sets defaults."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self.entry_url.delete(0, tk.END)
                self.entry_url.insert(0, data.get('server_url', LMSTUDIO_DEFAULT_URL))

                self.entry_path.delete(0, tk.END)
                self.entry_path.insert(0, data.get('folder_path', ''))

                self.txt_sys_instruction.delete('1.0', tk.END)
                self.txt_sys_instruction.insert(tk.END, data.get('system_instruction', ''))

                self.txt_prompt.delete('1.0', tk.END)
                self.txt_prompt.insert(tk.END, data.get('prompt', ''))

                # Load theme
                self.current_theme = data.get('theme', 'light')
                self.apply_theme()

                self.log("Configuration loaded.")
            except Exception as e:
                self.log(f"Error loading config: {e}")
                self.set_defaults()
        else:
            self.set_defaults()

    def set_defaults(self):
        self.entry_url.delete(0, tk.END)
        self.entry_url.insert(0, LMSTUDIO_DEFAULT_URL)

    def save_config(self, server_url, folder_path, sys_instruction, prompt):
        """Saves current UI settings to JSON, preserving theme."""
        data = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                pass
        data.update({
            "server_url": server_url,
            "folder_path": folder_path,
            "system_instruction": sys_instruction,
            "prompt": prompt
        })
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            self.log(f"Could not save config: {e}")

    def save_prompts(self):
        """Save current prompts and settings to config."""
        server_url = self.entry_url.get().strip() or LMSTUDIO_DEFAULT_URL
        folder_path = self.entry_path.get().strip()
        sys_instruction = self.txt_sys_instruction.get("1.0", tk.END).strip()
        prompt = self.txt_prompt.get("1.0", tk.END).strip()
        self.save_config(server_url, folder_path, sys_instruction, prompt)
        self.log("Prompts saved.")

    # --- IMAGE ENCODING ---
    @staticmethod
    def encode_image_base64(image_path):
        """Read an image file and return its base64-encoded string and MIME type."""
        ext = os.path.splitext(image_path)[1].lower()
        mime_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp',
        }
        mime_type = mime_map.get(ext, 'image/jpeg')
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8'), mime_type

    # --- STRIP THINKING TAGS ---
    @staticmethod
    def strip_thinking(text):
        """Remove <think>...</think> blocks from thinking-model output."""
        return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

    # --- PROCESSING LOGIC ---
    def start_thread(self):
        if self.is_running:
            return

        server_url = self.entry_url.get().strip() or LMSTUDIO_DEFAULT_URL
        folder_path = self.entry_path.get().strip()
        sys_instruction = self.txt_sys_instruction.get("1.0", tk.END).strip()
        prompt_text = self.txt_prompt.get("1.0", tk.END).strip()

        if not os.path.isdir(folder_path):
            messagebox.showerror("Error", "Invalid Folder Path.")
            return

        # Save config before starting
        self.save_config(server_url, folder_path, sys_instruction, prompt_text)

        self.is_running = True
        self.btn_start.config(state='disabled', text="Processing...")
        self.btn_stop.config(state='normal')

        thread = threading.Thread(
            target=self.process_images,
            args=(server_url, folder_path, sys_instruction, prompt_text)
        )
        thread.daemon = True
        thread.start()

    def process_images(self, server_url, folder_path, sys_instruction, prompt_text):
        self.log("--- Starting Process ---")
        self.log(f"Server: {server_url}")

        # Verify server is reachable
        try:
            r = requests.get(f"{server_url}/models", timeout=5)
            r.raise_for_status()
            models_data = r.json()
            model_id = models_data['data'][0]['id'] if models_data.get('data') else "local-model"
            self.log(f"Connected. Model: {model_id}")
        except Exception as e:
            self.log(f"Cannot reach LM Studio server: {e}")
            self.reset_ui()
            return

        # Get images
        try:
            image_files = sorted(
                f for f in os.listdir(folder_path) if f.lower().endswith(SUPPORTED_EXTENSIONS)
            )
        except Exception as e:
            self.log(f"Error reading folder: {e}")
            self.reset_ui()
            return

        if not image_files:
            self.log("No images found in folder.")
            self.reset_ui()
            return

        self.log(f"Found {len(image_files)} image(s).")
        processed_count = 0
        endpoint = f"{server_url}/chat/completions"

        for filename in image_files:
            if not self.is_running:
                break

            image_path = os.path.join(folder_path, filename)
            base_filename, _ = os.path.splitext(filename)
            caption_path = os.path.join(folder_path, f"{base_filename}.txt")

            if os.path.exists(caption_path):
                self.log(f"Skipping '{filename}' (caption exists).")
                continue

            try:
                self.log(f"Processing '{filename}'...")
                img_b64, mime_type = self.encode_image_base64(image_path)

                # Build messages
                messages = []
                if sys_instruction:
                    messages.append({"role": "system", "content": sys_instruction})

                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{img_b64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt_text
                        }
                    ]
                })

                payload = {
                    "model": model_id,
                    "messages": messages,
                }

                resp = requests.post(endpoint, json=payload, timeout=None)
                resp.raise_for_status()
                result = resp.json()

                raw_text = result['choices'][0]['message']['content']
                caption = self.strip_thinking(raw_text).replace('\n', ' ').strip()

                if not caption:
                    self.log(f"Warning: Empty caption for '{filename}', skipping.")
                    continue

                with open(caption_path, 'w', encoding='utf-8') as f:
                    f.write(caption)

                self.log(f"Done: '{filename}'")
                processed_count += 1

            except Exception as e:
                self.log(f"Error on '{filename}': {e}")

        self.log(f"\nFinished! Total processed: {processed_count}")
        self.reset_ui()

    def stop_processing(self):
        self.is_running = False
        self.log("Stop requested. Will finish current image and stop.")
        self.btn_stop.config(state='disabled')

    def reset_ui(self):
        def _update():
            self.is_running = False
            self.btn_start.config(state='normal', text="Start Captioning")
            self.btn_stop.config(state='disabled')
        self.root.after(0, _update)


if __name__ == "__main__":
    root = tk.Tk()
    app = CaptionApp(root)
    root.mainloop()