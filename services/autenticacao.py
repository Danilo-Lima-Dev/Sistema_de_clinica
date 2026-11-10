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
from services.validacoes import ErroValidacao, validar_login, validar_nome

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

# Papéis (os "crachás"): cada um define o que a pessoa pode fazer no sistema.
PAPEL_ADMIN = "Administrador"
PAPEL_ATENDENTE = "Atendente"
PAPEL_MEDICO = "Médico"
PAPEIS = (PAPEL_ADMIN, PAPEL_ATENDENTE, PAPEL_MEDICO)


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
    nome = validar_nome(nome, "O nome")
    login = validar_login(login)  # login não diferencia maiúsculas
    return nome, login


TAMANHO_MAXIMO_SENHA = 128


def _validar_senha(senha, login=None):
    """Senha: 6 a 128 caracteres, sem espaço no começo/fim e diferente do login."""
    senha = senha or ""
    if len(senha) < TAMANHO_MINIMO_SENHA:
        raise ErroValidacao(
            f"A senha deve ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres."
        )
    if len(senha) > TAMANHO_MAXIMO_SENHA:
        raise ErroValidacao(f"A senha deve ter no máximo {TAMANHO_MAXIMO_SENHA} caracteres.")
    if senha != senha.strip():
        raise ErroValidacao("A senha não pode começar nem terminar com espaço.")
    if login and senha.lower() == login:
        raise ErroValidacao("A senha não pode ser igual ao usuário (login).")


def _definir_papel(papel, superusuario):
    """Descobre o papel final. Sem papel, vale o jeito antigo: super usuário = Administrador."""
    if papel is None:
        papel = PAPEL_ADMIN if superusuario else PAPEL_ATENDENTE
    if papel not in PAPEIS:
        raise ErroValidacao("Escolha um papel válido: Administrador, Atendente ou Médico.")
    return papel


def _validar_vinculo_medico(con, papel, profissional_id, ignorar_usuario_id=None):
    """Só o Médico é ligado a um profissional; devolve o profissional_id a gravar (ou None)."""
    if papel != PAPEL_MEDICO:
        if profissional_id:
            raise ErroValidacao("Somente o papel Médico é ligado a um profissional.")
        return None
    if not profissional_id:
        raise ErroValidacao("Escolha qual profissional é este médico.")
    prof = con.execute(
        "SELECT ativo FROM profissional WHERE id = ?", (profissional_id,)
    ).fetchone()
    if prof is None:
        raise ErroValidacao("Profissional não encontrado.")
    if not prof["ativo"]:
        raise ErroValidacao("Este profissional está inativo.")
    outro = con.execute(
        "SELECT 1 FROM usuario WHERE profissional_id = ? AND id != ?",
        (profissional_id, ignorar_usuario_id or 0),
    ).fetchone()
    if outro:
        raise ErroValidacao("Este profissional já está ligado a outro usuário.")
    return profissional_id


def cadastrar_usuario(nome, login, senha, superusuario=False, papel=None, profissional_id=None):
    """Cria um usuário. Levanta ErroValidacao se algum dado for inválido.

    Esta função não confere permissão (serve para o script de linha de comando e para
    os testes). A tela usa `cadastrar_usuario_por`, que só aceita um Administrador.
    O papel manda: a coluna antiga `superusuario` fica 1 só para o Administrador.
    """
    nome, login = _validar_nome_login(nome, login)
    _validar_senha(senha, login)
    papel = _definir_papel(papel, superusuario)
    try:
        with database.transacao() as con:
            profissional_id = _validar_vinculo_medico(con, papel, profissional_id)
            con.execute(
                "INSERT INTO usuario (nome, login, senha_hash, superusuario, papel, profissional_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (nome, login, gerar_hash(senha), 1 if papel == PAPEL_ADMIN else 0,
                 papel, profissional_id),
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
def exigir_papel(executor_id, *papeis, mensagem="Você não tem permissão para esta ação."):
    """O "cadeado": confere NO BANCO se quem pede está ativo e tem um dos papéis permitidos.

    Se não tiver, levanta ErroValidacao. Se tiver, devolve (id, papel, profissional_id).
    A permissão é conferida aqui, no back-end, e não só escondendo botões na tela.
    """
    with database.transacao() as con:
        linha = con.execute(
            "SELECT id, papel, profissional_id, ativo FROM usuario WHERE id = ?", (executor_id,)
        ).fetchone()
    if linha is None or not linha["ativo"] or linha["papel"] not in papeis:
        raise ErroValidacao(mensagem)
    return {"id": linha["id"], "papel": linha["papel"], "profissional_id": linha["profissional_id"]}


def exigir_superusuario(executor_id, mensagem="Somente um super usuário pode gerenciar usuários."):
    """Exige o papel Administrador (nome antigo mantido: financeiro e especialidades usam)."""
    exigir_papel(executor_id, PAPEL_ADMIN, mensagem=mensagem)


def _exigir_superusuario(executor_id):
    exigir_superusuario(executor_id)


def listar_usuarios(executor_id):
    """Lista todos os usuários (sem o hash da senha). Só para super usuário."""
    _exigir_superusuario(executor_id)
    with database.transacao() as con:
        return con.execute(
            "SELECT id, nome, login, ativo, superusuario, papel, profissional_id "
            "FROM usuario ORDER BY nome COLLATE NOCASE"
        ).fetchall()


def cadastrar_usuario_por(executor_id, nome, login, senha, superusuario=False,
                          papel=None, profissional_id=None):
    """Cadastra um usuário em nome de um Administrador."""
    _exigir_superusuario(executor_id)
    cadastrar_usuario(nome, login, senha, superusuario, papel, profissional_id)


def atualizar_usuario(executor_id, id_usuario, nome, login, senha="", ativo=True,
                      superusuario=False, papel=None, profissional_id=None):
    """Altera nome, login, situação e perfil de um usuário; troca a senha se `senha` vier preenchida.

    Senha em branco = mantém a senha atual. Só um super usuário pode usar.
    """
    _exigir_superusuario(executor_id)
    nome, login = _validar_nome_login(nome, login)
    if senha:
        _validar_senha(senha, login)
    papel = _definir_papel(papel, superusuario)
    ativo, superusuario = (1 if ativo else 0), (1 if papel == PAPEL_ADMIN else 0)

    try:
        with database.transacao() as con:
            atual = con.execute(
                "SELECT superusuario, ativo FROM usuario WHERE id = ?", (id_usuario,)
            ).fetchone()
            if atual is None:
                raise ErroValidacao("Usuário não encontrado.")
            if id_usuario == executor_id and not ativo:
                raise ErroValidacao("Você não pode desativar o seu próprio usuário.")
            profissional_id = _validar_vinculo_medico(
                con, papel, profissional_id, ignorar_usuario_id=id_usuario
            )
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
            campos = "nome = ?, login = ?, ativo = ?, superusuario = ?, papel = ?, profissional_id = ?"
            valores = [nome, login, ativo, superusuario, papel, profissional_id]
            if senha:
                campos += ", senha_hash = ?"
                valores.append(gerar_hash(senha))
            con.execute(f"UPDATE usuario SET {campos} WHERE id = ?", (*valores, id_usuario))
    except sqlite3.IntegrityError:
        raise ErroValidacao("Já existe um usuário com esse login.") from None


def houve_mudanca_usuario(executor_id, id_usuario, nome, login, senha="", ativo=True,
                          papel=None, profissional_id=None):
    """Valida os dados e diz se diferem dos gravados (sem gravar). Só Administrador.

    Senha preenchida conta como mudança. Serve para a tela avisar "Nenhuma alteração".
    """
    _exigir_superusuario(executor_id)
    nome, login = _validar_nome_login(nome, login)
    if senha:
        _validar_senha(senha, login)
    papel = _definir_papel(papel, False)
    with database.transacao() as con:
        atual = con.execute(
            "SELECT nome, login, ativo, papel, profissional_id FROM usuario WHERE id = ?",
            (id_usuario,),
        ).fetchone()
        if atual is None:
            raise ErroValidacao("Usuário não encontrado.")
        profissional_id = _validar_vinculo_medico(
            con, papel, profissional_id, ignorar_usuario_id=id_usuario
        )
    return bool(
        senha or nome != atual["nome"] or login != atual["login"]
        or (1 if ativo else 0) != atual["ativo"] or papel != atual["papel"]
        or profissional_id != atual["profissional_id"]
    )


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

    Devolve um dicionário com os dados do usuário (id, nome, login, superusuario, papel, profissional_id) se estiver
    correto; senão levanta ErroValidacao. A mensagem é a mesma para "usuário não
    existe" e "senha errada", para não revelar quais logins existem.
    """
    login = (login or "").strip().lower()
    if not login or not senha:
        raise ErroValidacao("Informe o usuário e a senha.")

    with database.transacao() as con:
        linha = con.execute(
            "SELECT id, nome, login, senha_hash, ativo, superusuario, papel, profissional_id "
            "FROM usuario WHERE login = ?",
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
        "papel": linha["papel"], "profissional_id": linha["profissional_id"],
    }