"""Menu de pacientes no terminal (cadastrar, listar, buscar, alterar e excluir).

Este arquivo só cuida de perguntar e mostrar. As validações e o SQL ficam em
`services/pacientes.py`, o mesmo código que a versão gráfica usava.
"""
import sqlite3

from cli.entrada import confirmar, ler_inteiro, ler_texto, pausar, titulo
from services import pacientes
from services.validacoes import (
    ErroValidacao,
    formatar_cpf,
    formatar_telefone,
    iso_para_data_br,
    mascara_data,
    somente_digitos,
)

DADOS_VAZIOS = {"nome": "", "cpf": "", "nascimento": "", "telefone": "", "email": ""}


# ---------------------------------------------------------------- exibição
def mostrar_tabela(lista):
    """Imprime a lista de pacientes em forma de tabela."""
    if not lista:
        print("\nNenhum paciente encontrado.")
        return
    cabecalho = (
        f"{'ID':<4} {'Nome':<28} {'CPF':<14} {'Nascimento':<11} {'Telefone':<15} E-mail"
    )
    print()
    print(cabecalho)
    print("-" * (len(cabecalho) + 10))
    for p in lista:
        print(
            f"{p['id']:<4} {p['nome'][:28]:<28} {formatar_cpf(p['cpf']):<14} "
            f"{iso_para_data_br(p['data_nascimento']):<11} "
            f"{formatar_telefone(p['telefone']):<15} {p['email'] or ''}"
        )
    print(f"\n{len(lista)} paciente(s).")


# ------------------------------------------------------------ entrada de dados
def pedir_dados(atuais):
    """Pergunta os campos do paciente. Enter mantém o valor entre colchetes."""
    nome = ler_texto("Nome", atuais["nome"])
    cpf = somente_digitos(ler_texto("CPF (só números)", atuais["cpf"]))
    nascimento = mascara_data(ler_texto("Nascimento (DD/MM/AAAA)", atuais["nascimento"]))
    telefone = somente_digitos(ler_texto("Telefone com DDD (opcional)", atuais["telefone"]))
    email = ler_texto("E-mail (opcional)", atuais["email"])
    return {
        "nome": nome,
        "cpf": cpf,
        "nascimento": nascimento,
        "telefone": telefone,
        "email": email,
    }


def preencher_e_salvar(atuais, salvar):
    """Pede os dados e tenta salvar.

    Se algum dado for inválido, mostra o motivo e deixa o usuário corrigir
    sem digitar tudo de novo (o que ele digitou vira o valor padrão).
    Devolve True se salvou e False se o usuário desistiu.
    """
    while True:
        dados = pedir_dados(atuais)
        try:
            salvar(**dados)
        except ErroValidacao as erro:
            print(f"\n[ATENÇÃO] {erro}")
            if not confirmar("Deseja corrigir os dados"):
                print("Operação cancelada.")
                return False
            atuais = dados
            print("(Enter mantém o valor entre colchetes)")
        except sqlite3.Error as erro:
            print(f"\n[ERRO NO BANCO DE DADOS] Não foi possível salvar: {erro}")
            return False
        else:
            return True


def escolher_paciente(acao):
    """Mostra a lista e pede o ID. Devolve o paciente (dict) ou None."""
    lista = pacientes.listar()
    if not lista:
        print("\nNenhum paciente cadastrado.")
        return None
    mostrar_tabela(lista)
    print()
    id_escolhido = ler_inteiro(f"ID do paciente que deseja {acao} (0 para cancelar)")
    if id_escolhido is None:  # não digitou um número (o aviso já foi mostrado)
        return None
    if id_escolhido == 0:
        print("Operação cancelada.")
        return None
    for paciente in lista:
        if paciente["id"] == id_escolhido:
            return paciente
    print(f"Não existe paciente com o ID {id_escolhido}.")
    return None


# ------------------------------------------------------------------- ações
def cadastrar():
    titulo("CADASTRAR PACIENTE")
    print("Campos obrigatórios: nome, CPF e nascimento.\n")
    if preencher_e_salvar(DADOS_VAZIOS, pacientes.cadastrar):
        print("\n[OK] Paciente cadastrado com sucesso.")


def listar():
    titulo("LISTA DE PACIENTES")
    try:
        mostrar_tabela(pacientes.listar())
    except sqlite3.Error as erro:
        print(f"\n[ERRO NO BANCO DE DADOS] Não foi possível listar: {erro}")


def buscar():
    titulo("BUSCAR PACIENTE")
    termo = ler_texto("Digite parte do nome ou do CPF")
    try:
        mostrar_tabela(pacientes.listar(termo))
    except sqlite3.Error as erro:
        print(f"\n[ERRO NO BANCO DE DADOS] Não foi possível buscar: {erro}")


def alterar():
    titulo("ALTERAR PACIENTE")
    paciente = escolher_paciente("alterar")
    if paciente is None:
        return
    atuais = {
        "nome": paciente["nome"],
        "cpf": paciente["cpf"],
        "nascimento": iso_para_data_br(paciente["data_nascimento"]),
        "telefone": paciente["telefone"] or "",
        "email": paciente["email"] or "",
    }
    print("\nEnter mantém o valor entre colchetes; '-' limpa um campo opcional.\n")

    def salvar(**dados):
        pacientes.atualizar(paciente["id"], **dados)

    if preencher_e_salvar(atuais, salvar):
        print("\n[OK] Dados do paciente atualizados com sucesso.")


def excluir():
    titulo("EXCLUIR PACIENTE")
    paciente = escolher_paciente("excluir")
    if paciente is None:
        return
    if not confirmar(f"\nExcluir o paciente '{paciente['nome']}'"):
        print("Exclusão cancelada.")
        return
    try:
        pacientes.excluir(paciente["id"])
    except ErroValidacao as erro:
        print(f"\n[ATENÇÃO] {erro}")
    except sqlite3.Error as erro:
        print(f"\n[ERRO NO BANCO DE DADOS] Não foi possível excluir: {erro}")
    else:
        print("\n[OK] Paciente excluído com sucesso.")


# --------------------------------------------------------------------- menu
def menu_pacientes():
    opcoes = {
        "1": ("Cadastrar paciente", cadastrar),
        "2": ("Listar pacientes", listar),
        "3": ("Buscar paciente (nome ou CPF)", buscar),
        "4": ("Alterar paciente", alterar),
        "5": ("Excluir paciente", excluir),
    }
    while True:
        titulo("PACIENTES")
        for numero, (texto, _funcao) in opcoes.items():
            print(f"  {numero} - {texto}")
        print("  0 - Voltar")
        escolha = input("\nEscolha uma opção: ").strip()
        if escolha == "0":
            return
        if escolha in opcoes:
            opcoes[escolha][1]()
            pausar()
        else:
            print("\nOpção inválida. Digite um dos números do menu.")
