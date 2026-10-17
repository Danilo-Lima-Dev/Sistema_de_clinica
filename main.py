"""Ponto de entrada do Sistema de Clínica.

Execute com:  python main.py
(antes, uma vez:  pip install customtkinter)
"""
import database
from services import autenticacao
from ui.app import App


def main():
    database.criar_tabelas()             # cria o banco na primeira execução
    autenticacao.criar_usuario_padrao()  # cria o "admin" se ainda não houver usuários
    App().mainloop()                     # a janela começa pela tela de login


if __name__ == "__main__":
    main()
