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

# Super usuário criado automaticamente (se ainda não existir nenhum): é o único tipo
# de usuário que cadastra e altera os outros. TROQUE A SENHA depois do primeiro acesso.
SUPER_NOME = "Super Usuário"
SUPER_LOGIN = "super"
SUPER_SENHA = "super123"


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
def _validar_nome_login(nome, login):
    """Limpa e confere nome e login. Devolve (nome, login)."""
    nome = (nome or "").strip()
    login = (login or "").strip().lower()  # login não diferencia maiúsculas
    if not nome:
        raise ErroValidacao("O nome é obrigatório.")
    if not login:
        raise ErroValidacao("O usuário é obrigatório.")
    return nome, login


def _validar_senha(senha):
    if len(senha or "") < TAMANHO_MINIMO_SENHA:
        raise ErroValidacao(
            f"A senha deve ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres."
        )


def cadastrar_usuario(nome, login, senha, superusuario=False):
    """Cria um usuário. Levanta ErroValidacao se algum dado for inválido.

    Esta função não confere permissão (serve para o script de linha de comando e para
    os testes). A tela usa `cadastrar_usuario_por`, que só aceita um super usuário.
    """
    nome, login = _validar_nome_login(nome, login)
    _validar_senha(senha)
    try:
        with database.transacao() as con:
            con.execute(
                "INSERT INTO usuario (nome, login, senha_hash, superusuario) VALUES (?, ?, ?, ?)",
                (nome, login, gerar_hash(senha), 1 if superusuario else 0),
            )
    except sqlite3.IntegrityError:
        raise ErroValidacao("Já existe um usuário com esse login.") from None


def criar_usuario_padrao():
    """Se o banco ainda não tem nenhum usuário, cria o administrador padrão."""
    with database.transacao() as con:
        total = con.execute("SELECT COUNT(*) FROM usuario").fetchone()[0]
    if total == 0:
        cadastrar_usuario("Administrador", USUARIO_PADRAO, SENHA_PADRAO)


def criar_superusuario_padrao():
    """Se ainda não existe nenhum super usuário, cria o padrão (login `super`)."""
    with database.transacao() as con:
        total = con.execute("SELECT COUNT(*) FROM usuario WHERE superusuario = 1").fetchone()[0]
        login_ocupado = con.execute(
            "SELECT 1 FROM usuario WHERE login = ?", (SUPER_LOGIN,)
        ).fetchone()
    if total == 0 and not login_ocupado:
        cadastrar_usuario(SUPER_NOME, SUPER_LOGIN, SUPER_SENHA, superusuario=True)


# ------------------------------------------------- gerência (só super usuário)
def exigir_superusuario(executor_id, mensagem="Somente um super usuário pode gerenciar usuários."):
    """Confere NO BANCO se quem pede ainda é um super usuário ativo (senão levanta ErroValidacao).

    Usada também pelo financeiro e pelos valores das especialidades: a permissão é conferida
    aqui, no back-end, e não só escondendo botões na tela.
    """
    with database.transacao() as con:
        linha = con.execute(
            "SELECT superusuario, ativo FROM usuario WHERE id = ?", (executor_id,)
        ).fetchone()
    if linha is None or not linha["superusuario"] or not linha["ativo"]:
        raise ErroValidacao(mensagem)


def _exigir_superusuario(executor_id):
    exigir_superusuario(executor_id)


def listar_usuarios(executor_id):
    """Lista todos os usuários (sem o hash da senha). Só para super usuário."""
    _exigir_superusuario(executor_id)
    with database.transacao() as con:
        return con.execute(
            "SELECT id, nome, login, ativo, superusuario FROM usuario ORDER BY nome COLLATE NOCASE"
        ).fetchall()


def cadastrar_usuario_por(executor_id, nome, login, senha, superusuario=False):
    """Cadastra um usuário em nome de um super usuário."""
    _exigir_superusuario(executor_id)
    cadastrar_usuario(nome, login, senha, superusuario)


def atualizar_usuario(executor_id, id_usuario, nome, login, senha="", ativo=True, superusuario=False):
    """Altera nome, login, situação e perfil de um usuário; troca a senha se `senha` vier preenchida.

    Senha em branco = mantém a senha atual. Só um super usuário pode usar.
    """
    _exigir_superusuario(executor_id)
    nome, login = _validar_nome_login(nome, login)
    if senha:
        _validar_senha(senha)
    ativo, superusuario = (1 if ativo else 0), (1 if superusuario else 0)

    try:
        with database.transacao() as con:
            atual = con.execute(
                "SELECT superusuario, ativo FROM usuario WHERE id = ?", (id_usuario,)
            ).fetchone()
            if atual is None:
                raise ErroValidacao("Usuário não encontrado.")
            if id_usuario == executor_id and not ativo:
                raise ErroValidacao("Você não pode desativar o seu próprio usuário.")
            era_super_ativo = atual["superusuario"] and atual["ativo"]
            if era_super_ativo and not (superusuario and ativo):
                restantes = con.execute(
                    "SELECT COUNT(*) FROM usuario WHERE superusuario = 1 AND ativo = 1 AND id != ?",
                    (id_usuario,),
                ).fetchone()[0]
                if restantes == 0:
                    raise ErroValidacao(
                        "Deve existir pelo menos um super usuário ativo no sistema."
                    )
            campos = "nome = ?, login = ?, ativo = ?, superusuario = ?"
            valores = [nome, login, ativo, superusuario]
            if senha:
                campos += ", senha_hash = ?"
                valores.append(gerar_hash(senha))
            con.execute(f"UPDATE usuario SET {campos} WHERE id = ?", (*valores, id_usuario))
    except sqlite3.IntegrityError:
        raise ErroValidacao("Já existe um usuário com esse login.") from None


def excluir_usuario(executor_id, id_usuario):
    """Exclui um usuário de vez. Só um super usuário pode; ninguém exclui o próprio usuário."""
    _exigir_superusuario(executor_id)
    if id_usuario == executor_id:
        raise ErroValidacao("Você não pode excluir o seu próprio usuário.")
    with database.transacao() as con:
        alvo = con.execute(
            "SELECT superusuario, ativo FROM usuario WHERE id = ?", (id_usuario,)
        ).fetchone()
        if alvo is None:
            raise ErroValidacao("Usuário não encontrado.")
        if alvo["superusuario"] and alvo["ativo"]:
            restantes = con.execute(
                "SELECT COUNT(*) FROM usuario WHERE superusuario = 1 AND ativo = 1 AND id != ?",
                (id_usuario,),
            ).fetchone()[0]
            if restantes == 0:
                raise ErroValidacao("Deve existir pelo menos um super usuário ativo no sistema.")
        con.execute("DELETE FROM usuario WHERE id = ?", (id_usuario,))


def autenticar(login, senha):
    """Confere login e senha.

    Devolve um dicionário com os dados do usuário (id, nome, login, superusuario) se estiver
    correto; senão levanta ErroValidacao. A mensagem é a mesma para "usuário não
    existe" e "senha errada", para não revelar quais logins existem.
    """
    login = (login or "").strip().lower()
    if not login or not senha:
        raise ErroValidacao("Informe o usuário e a senha.")

    with database.transacao() as con:
        linha = con.execute(
            "SELECT id, nome, login, senha_hash, ativo, superusuario FROM usuario WHERE login = ?",
            (login,),
        ).fetchone()

    if linha is None:
        gerar_hash(senha)  # gasta o mesmo tempo, para não denunciar login inexistente
        raise ErroValidacao("Usuário ou senha incorretos.")
    if not conferir_senha(senha, linha["senha_hash"]):
        raise ErroValidacao("Usuário ou senha incorretos.")
    if not linha["ativo"]:
        raise ErroValidacao("Este usuário está desativado.")

    return {
        "id": linha["id"], "nome": linha["nome"], "login": linha["login"],
        "superusuario": bool(linha["superusuario"]),
    }
