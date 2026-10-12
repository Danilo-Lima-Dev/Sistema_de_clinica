"""Funções de validação e formatação (CPF, datas, telefone, e-mail).

Padrão brasileiro: datas em DD/MM/AAAA e CPF digitado apenas com números.
No banco, as datas são guardadas como AAAA-MM-DD (ISO), que ordena corretamente.
"""
import re
from datetime import date, datetime


class ErroValidacao(Exception):
    """Erro de validação de campo ou de regra de negócio.

    A mensagem já vem pronta para ser mostrada ao usuário.
    """


# ---------------------------------------------------------------- números
def somente_digitos(texto):
    """Remove tudo que não for número. Aceita None."""
    return re.sub(r"\D", "", texto or "")


# -------------------------------------------------------------------- CPF
def cpf_valido(cpf):
    """Confere os 11 números e os dois dígitos verificadores do CPF."""
    cpf = somente_digitos(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11 % 10
        if digito != int(cpf[tamanho]):
            return False
    return True


def formatar_cpf(cpf):
    """12345678909 -> 123.456.789-09 (só para exibição)."""
    c = somente_digitos(cpf)
    if len(c) != 11:
        return c
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"


# --------------------------------------------------------------- telefone
def telefone_valido(telefone):
    """Telefone com DDD: 10 dígitos (fixo) ou 11 (celular)."""
    return len(somente_digitos(telefone)) in (10, 11)


def formatar_telefone(telefone):
    """11987654321 -> (11) 98765-4321 (só para exibição)."""
    t = somente_digitos(telefone)
    if len(t) == 11:
        return f"({t[:2]}) {t[2:7]}-{t[7:]}"
    if len(t) == 10:
        return f"({t[:2]}) {t[2:6]}-{t[6:]}"
    return t


# ----------------------------------------------------------------- e-mail
def email_valido(email):
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or "") is not None


# ------------------------------------------------------------------ datas
def mascara_data(texto):
    """Digitou 25031990 -> 25/03/1990 (usado enquanto o usuário digita)."""
    d = somente_digitos(texto)[:8]
    if len(d) <= 2:
        return d
    if len(d) <= 4:
        return f"{d[:2]}/{d[2:]}"
    return f"{d[:2]}/{d[2:4]}/{d[4:]}"


def data_br_para_date(texto):
    """Converte 'DD/MM/AAAA' em date. Levanta ErroValidacao se for inválida."""
    texto = (texto or "").strip()
    mensagem = "Data inválida. Use o formato DD/MM/AAAA, por exemplo 25/03/1990."
    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", texto):
        raise ErroValidacao(mensagem)
    try:
        return datetime.strptime(texto, "%d/%m/%Y").date()
    except ValueError:  # ex.: 31/02/2000
        raise ErroValidacao(mensagem)


def date_para_br(data):
    """date -> 'DD/MM/AAAA'."""
    return data.strftime("%d/%m/%Y")


def iso_para_data_br(texto_iso):
    """'AAAA-MM-DD' (do banco) -> 'DD/MM/AAAA' (para a tela)."""
    return date_para_br(date.fromisoformat(texto_iso))
