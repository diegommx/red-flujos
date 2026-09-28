"""Ventana para iniciar el proyecto con un botón, sin usar la consola."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox
import webbrowser

from launcher_core import launch_server, prepare_environment, wait_until_ready


class Iniciador:
    def __init__(self) -> None:
        self.window = tk.Tk()
        self.window.title("Red de flujos")
        self.window.geometry("420x185")
        self.window.resizable(False, False)
        self.process = None
        self.url = ""
        self.starting = False
        self.closing = False

        frame = tk.Frame(self.window, padx=24, pady=18)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="Red de flujos", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(frame, text="Explora la demostración o elige tus propios datos.",
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 14))
        row = tk.Frame(frame)
        row.pack(anchor="w")
        self.start_button = tk.Button(row, text="Iniciar proyecto", command=self.start, width=18)
        self.start_button.pack(side="left", padx=(0, 8))
        self.open_button = tk.Button(row, text="Abrir navegador", command=self.open_browser,
                                     state="disabled")
        self.open_button.pack(side="left", padx=(0, 8))
        self.stop_button = tk.Button(row, text="Detener", command=self.stop, state="disabled")
        self.stop_button.pack(side="left")
        self.status = tk.StringVar(value="Listo para iniciar. El primer uso puede tardar unos minutos.")
        tk.Label(frame, textvariable=self.status, wraplength=370, justify="left",
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(16, 0))
        self.window.protocol("WM_DELETE_WINDOW", self.close)

    def set_status(self, value: str) -> None:
        if not self.closing:
            self.window.after(0, lambda: self.status.set(value))

    def start(self) -> None:
        if self.starting or (self.process and self.process.poll() is None):
            return
        self.starting = True
        self.start_button.config(state="disabled")
        self.set_status("Preparando la aplicación…")
        threading.Thread(target=self._start_worker, daemon=True).start()

    def _start_worker(self) -> None:
        try:
            prepare_environment(self.set_status)
            if self.closing:
                return
            self.set_status("Iniciando el servidor local…")
            process, url = launch_server()
            self.process = process
            if self.closing:
                process.terminate()
                return
            wait_until_ready(process, url)
            if self.closing:
                process.terminate()
                return
            self.window.after(0, lambda: self._ready(url))
        except Exception as exc:
            if self.process and self.process.poll() is None:
                self.process.terminate()
            if not self.closing:
                self.window.after(0, lambda error=str(exc): self._failed(error))

    def _ready(self, url: str) -> None:
        self.starting = False
        self.url = url
        self.status.set("Aplicación abierta en este equipo. Elige la demo o tus datos en el navegador.")
        self.open_button.config(state="normal")
        self.stop_button.config(state="normal")
        self.open_browser()

    def _failed(self, error: str) -> None:
        self.starting = False
        self.start_button.config(state="normal")
        self.status.set("No se pudo iniciar la aplicación.")
        messagebox.showerror("Red de flujos", error)

    def open_browser(self) -> None:
        if self.url:
            webbrowser.open(self.url)

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
        self.process = None
        self.url = ""
        self.start_button.config(state="normal")
        self.open_button.config(state="disabled")
        self.stop_button.config(state="disabled")
        self.status.set("Aplicación detenida.")

    def close(self) -> None:
        self.closing = True
        self.stop()
        self.window.destroy()


if __name__ == "__main__":
    Iniciador().window.mainloop()
