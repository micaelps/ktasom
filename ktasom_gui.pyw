#!/usr/bin/env python3
"""Interface gráfica do ktasom."""
import os
import queue
import sys
import threading
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ModuleNotFoundError:
    sys.exit("erro: Tkinter não encontrado. No Debian e no Ubuntu: sudo apt install python3-tk")

from ktasom import DownloadJob, missing_tools, read_links

EVENTS_POLL_MS = 100


class App:
    def __init__(self, root):
        self.root = root
        self.job = None
        self.events = queue.Queue()
        self.event_handlers = {"link": self.on_link, "line": self.status_changed, "done": self.on_done}
        self.source = tk.StringVar()
        self.output = tk.StringVar(value=str(Path.home()))
        self.status = tk.StringVar(value="Pronto")
        self.build_window()
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.poll_events()

    def build_window(self):
        self.root.title("ktasom")
        self.root.minsize(560, 360)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        frame = ttk.Frame(self.root, padding=16)
        frame.grid(sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(7, weight=1)

        ttk.Label(frame, text="Link do YouTube ou arquivo CSV").grid(row=0, columnspan=2, sticky="w")
        source_entry = ttk.Entry(frame, textvariable=self.source)
        source_entry.grid(row=1, column=0, sticky="ew", pady=(4, 12))
        ttk.Button(frame, text="Escolher CSV", command=self.choose_csv).grid(row=1, column=1, padx=(8, 0), pady=(4, 12))

        ttk.Label(frame, text="Salvar MP3s em").grid(row=2, columnspan=2, sticky="w")
        ttk.Entry(frame, textvariable=self.output).grid(row=3, column=0, sticky="ew", pady=(4, 12))
        ttk.Button(frame, text="Escolher pasta", command=self.choose_output).grid(row=3, column=1, padx=(8, 0), pady=(4, 12))

        self.download_button = ttk.Button(frame, text="Baixar", command=self.start)
        self.download_button.grid(row=4, columnspan=2, sticky="ew")
        self.progress = ttk.Progressbar(frame)
        self.progress.grid(row=5, columnspan=2, sticky="ew", pady=(12, 4))
        ttk.Label(frame, textvariable=self.status).grid(row=6, columnspan=2, sticky="w")
        self.log_view = tk.Text(frame, height=8, state="disabled", wrap="word")
        self.log_view.grid(row=7, columnspan=2, sticky="nsew", pady=(8, 0))
        source_entry.focus()

    def choose_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Todos os arquivos", "*")])
        if path:
            self.source.set(path)

    def choose_output(self):
        path = filedialog.askdirectory(initialdir=self.output.get())
        if path:
            self.output.set(path)

    def start(self):
        missing = missing_tools()
        if missing:
            return self.show_error(f"Não encontrado: {', '.join(missing)}. Coloque na pasta do ktasom ou no PATH.")
        source = self.source.get().strip()
        if not source:
            return self.show_error("Informe um link do YouTube ou escolha um arquivo CSV.")
        output_dir = Path(self.output.get()).expanduser()
        try:
            links = read_links(source)
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            return self.show_error(f"Não foi possível usar {error.filename}: {error.strerror}")
        if not links:
            return self.show_error(f"Nenhum link do YouTube encontrado em {source}.")

        self.log_view.configure(state="normal")
        self.log_view.delete("1.0", "end")
        self.log_view.configure(state="disabled")
        self.download_button.configure(state="disabled")
        self.progress.configure(maximum=len(links), value=0)
        self.job = DownloadJob(links, output_dir, lambda *event: self.events.put(event))
        threading.Thread(target=self.job.run, daemon=True).start()

    def show_error(self, message):
        messagebox.showerror("ktasom", message)

    def poll_events(self):
        while not self.events.empty():
            kind, *data = self.events.get()
            self.event_handlers[kind](*data)
        self.root.after(EVENTS_POLL_MS, self.poll_events)

    def on_link(self, position, total, link):
        self.progress.configure(value=position - 1)
        self.log(f"[{position}/{total}] {link}")

    def status_changed(self, line):
        self.status.set(line)
        if line.startswith("ERROR"):
            self.log(line)

    def on_done(self, failed):
        self.progress.configure(value=self.progress["maximum"])
        total = int(self.progress["maximum"])
        summary = f"{total - len(failed)}/{total} links baixados em {self.job.output_dir}"
        self.status.set(summary)
        self.log(summary)
        if failed:
            self.log("Falharam:\n" + "\n".join(failed))
        self.download_button.configure(state="normal")
        self.job = None

    def log(self, message):
        self.log_view.configure(state="normal")
        self.log_view.insert("end", message + "\n")
        self.log_view.see("end")
        self.log_view.configure(state="disabled")

    def close(self):
        if self.job:
            self.job.cancel()
        self.root.destroy()


def main():
    os.environ["PATH"] = str(Path(__file__).resolve().parent) + os.pathsep + os.environ["PATH"]
    root = tk.Tk()
    if sys.platform == "linux":
        ttk.Style(root).theme_use("clam")
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
