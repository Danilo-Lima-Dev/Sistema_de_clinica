"""Janela principal do sistema."""
import tkinter as tk
from tkinter import ttk

from ui.tela_pacientes import TelaPacientes
from ui.telas_prototipo import TelaConsultas, TelaProfissionais


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Clínica")
        self.geometry("900x650")
        self.minsize(800, 560)

        abas = ttk.Notebook(self)
        abas.pack(fill="both", expand=True, padx=8, pady=8)
        abas.add(TelaPacientes(abas), text="Pacientes")
        abas.add(TelaProfissionais(abas), text="Profissionais (protótipo)")
        abas.add(TelaConsultas(abas), text="Consultas (protótipo)")
