"""Ponto de entrada do Sistema de Clínica.

Execute com:  python main.py
"""
import database
from ui.app import App


def main():
    database.criar_tabelas()  # cria o banco na primeira execução
    App().mainloop()


if __name__ == "__main__":
    main()
