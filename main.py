"""Ponto de entrada do Sistema de Clínica (versão de terminal).

Execute com:  python main.py
"""
import database
from cli.app import executar


def main():
    database.criar_tabelas()  # cria o banco na primeira execução
    executar()


if __name__ == "__main__":
    main()
