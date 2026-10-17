"""Regras de negócio do login: cadastro de usuários e conferência de senha.

A senha nunca é guardada em texto puro. Usamos PBKDF2 (biblioteca padrão do
Python, não precisa instalar nada) com um "salt" aleatório para cada usuário.
No banco, a coluna `senha_hash` guarda o texto  "salt$hash"  (ambos em hexadecimal).
"""
import hashlib
import hmac
import os
import sqlite3

import database
from services.validacoes import ErroValidacao

# Quantas vezes o PBKDF2 repete o cálculo (quanto maior, mais difícil de quebrar).
ITERACOES = 200_000
TAMANHO_MINIMO_SENHA = 6

# Usuário criado automaticamente na primeira execução (troque a senha depois!).
USUARIO_PADRAO = "admin"
SENHA_PADRAO = "admin123"


# ------------------------------------------------------------------ hash
def gerar_hash(senha, salt=None):
    """Transforma a senha em "salt$hash". Se não vier salt, cria um novo."""
    if salt is None:
        salt = os.urandom(16)  # 16 bytes aleatórios, diferentes para cada usuário
    hash_bytes = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, ITERACOES)
    return f"{salt.hex()}${hash_bytes.hex()}"


def conferir_senha(senha, senha_hash):
    """Diz se a senha digitada corresponde ao hash guardado no banco."""
    try:
        salt_hex, _ = senha_hash.split("$")
        novo = gerar_hash(senha, bytes.fromhex(salt_hex))
    except ValueError:  # hash corrompido ou fora do formato
        return False
    # compare_digest compara sem vazar informação pelo tempo de resposta
    return hmac.compare_digest(novo, senha_hash)


# --------------------------------------------------------------- usuários
def cadastrar_usuario(nome, login, senha):
    """Cria um usuário. Levanta ErroValidacao se algum dado for inválido."""
    nome = (nome or "").strip()
    login = (login or "").strip().lower()  # login não diferencia maiúsculas
    if not nome:
        raise ErroValidacao("O nome é obrigatório.")
    if not login:
        raise ErroValidacao("O usuário é obrigatório.")
    if len(senha or "") < TAMANHO_MINIMO_SENHA:
        raise ErroValidacao(
            f"A senha deve ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres."
        )
    try:
        with database.transacao() as con:
            con.execute(
                "INSERT INTO usuario (nome, login, senha_hash) VALUES (?, ?, ?)",
                (nome, login, gerar_hash(senha)),
            )
    except sqlite3.IntegrityError:
        raise ErroValidacao("Já existe um usuário com esse login.") from None


def criar_usuario_padrao():
    """Se o banco ainda não tem nenhum usuário, cria o administrador padrão."""
    with database.transacao() as con:
        total = con.execute("SELECT COUNT(*) FROM usuario").fetchone()[0]
    if total == 0:
        cadastrar_usuario("Administrador", USUARIO_PADRAO, SENHA_PADRAO)


def autenticar(login, senha):
    """Confere login e senha.

    Devolve um dicionário com os dados do usuário (id, nome, login) se estiver
    correto; senão levanta ErroValidacao. A mensagem é a mesma para "usuário não
    existe" e "senha errada", para não revelar quais logins existem.
    """
    login = (login or "").strip().lower()
    if not login or not senha:
        raise ErroValidacao("Informe o usuário e a senha.")

    with database.transacao() as con:
        linha = con.execute(
            "SELECT id, nome, login, senha_hash, ativo FROM usuario WHERE login = ?",
            (login,),
        ).fetchone()

    if linha is None:
        gerar_hash(senha)  # gasta o mesmo tempo, para não denunciar login inexistente
        raise ErroValidacao("Usuário ou senha incorretos.")
    if not conferir_senha(senha, linha["senha_hash"]):
        raise ErroValidacao("Usuário ou senha incorretos.")
    if not linha["ativo"]:
        raise ErroValidacao("Este usuário está desativado.")

    return {"id": linha["id"], "nome": linha["nome"], "login": linha["login"]}
