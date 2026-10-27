"""Funções de validação e formatação (CPF, datas, telefone, e-mail).

Padrão brasileiro: datas em DD/MM/AAAA e CPF digitado apenas com números.
No banco, as datas são guardadas como AAAA-MM-DD (ISO), que ordena corretamente.
"""
import re
import unicodedata
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
# Biblioteca baseada no libphonenumber do Google (pip install phonenumbers).
# Se ela não estiver instalada, o sistema continua funcionando com as regras
# próprias abaixo (DDD existente, 9 no início do celular, 2 a 5 no início do fixo).
try:
    import phonenumbers
except ImportError:  # pragma: no cover - depende do ambiente
    phonenumbers = None

# DDDs que existem no Brasil.
DDDS_VALIDOS = frozenset(
    "11 12 13 14 15 16 17 18 19 21 22 24 27 28 31 32 33 34 35 37 38 "
    "41 42 43 44 45 46 47 48 49 51 53 54 55 61 62 63 64 65 66 67 68 69 "
    "71 73 74 75 77 79 81 82 83 84 85 86 87 88 89 91 92 93 94 95 96 97 98 99".split()
)

MSG_TELEFONE = "Telefone inválido. Digite o DDD e o número (10 ou 11 dígitos)."


def _repetido_ou_sequencial(digitos):
    """True para 00000000, 99999999, 12345678, 87654321 (e variações com o 9 → 0)."""
    if len(digitos) < 2:
        return False
    if len(set(digitos)) == 1:
        return True
    passos = {(int(b) - int(a)) % 10 for a, b in zip(digitos, digitos[1:])}
    return passos == {1} or passos == {9}  # sempre +1 (crescente) ou sempre -1 (decrescente)


def motivo_telefone_invalido(telefone):
    """Devolve a mensagem de erro do telefone, ou None se ele estiver correto.

    Regras: DDD + 8 ou 9 dígitos; DDD existente; celular (9 dígitos, começa com 9)
    ou fixo (8 dígitos, começa com 2 a 5); sem números repetidos ou sequenciais;
    e, se a biblioteca `phonenumbers` estiver instalada, numeração plausível para o Brasil.
    """
    d = somente_digitos(telefone)
    if len(d) not in (10, 11):
        return MSG_TELEFONE
    ddd, numero = d[:2], d[2:]
    if ddd not in DDDS_VALIDOS:
        return f"DDD {ddd} não existe. Confira o telefone."
    # confere o número inteiro e também sem o 9 inicial do celular
    if _repetido_ou_sequencial(numero) or _repetido_ou_sequencial(numero[-8:]):
        return "Telefone inválido: número repetido ou sequencial (ex.: 12345678)."
    if len(numero) == 9 and numero[0] != "9":
        return "Celular inválido: o número deve começar com 9 depois do DDD."
    if len(numero) == 8 and numero[0] not in "2345":
        return "Telefone fixo inválido: o número deve começar com 2, 3, 4 ou 5 depois do DDD."
    if phonenumbers is not None:
        try:
            analisado = phonenumbers.parse(f"+55{d}", None)
            tipo = phonenumbers.number_type(analisado)
            tipos_aceitos = (
                phonenumbers.PhoneNumberType.MOBILE,
                phonenumbers.PhoneNumberType.FIXED_LINE,
                phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,
            )
            if not phonenumbers.is_valid_number(analisado) or tipo not in tipos_aceitos:
                return "Telefone inválido: essa numeração não existe. Confira os números."
        except phonenumbers.NumberParseException:
            return MSG_TELEFONE
    return None


def telefone_valido(telefone):
    """True se o telefone (DDD + número) passa em todas as regras de `motivo_telefone_invalido`."""
    return motivo_telefone_invalido(telefone) is None


def formatar_telefone(telefone):
    """11987654321 -> (11) 98765-4321 (só para exibição)."""
    t = somente_digitos(telefone)
    if len(t) == 11:
        return f"({t[:2]}) {t[2:7]}-{t[7:]}"
    if len(t) == 10:
        return f"({t[:2]}) {t[2:6]}-{t[6:]}"
    return t


def mascara_telefone(texto):
    """Máscara enquanto digita: 86999999999 -> (86) 99999-9999 (só aceita números)."""
    d = somente_digitos(texto)[:11]
    if not d:
        return ""
    if len(d) <= 2:
        return f"({d}"
    if len(d) <= 6:
        return f"({d[:2]}) {d[2:]}"
    if len(d) <= 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return f"({d[:2]}) {d[2:7]}-{d[7:]}"


# ----------------------------------------------------------------- e-mail
_EMAIL = re.compile(
    r"[A-Za-z0-9._%+\-]+@(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,}"
)

MSG_EMAIL = "E-mail inválido. Exemplo: nome@dominio.com"


def email_valido(email):
    """Confere o formato nome@dominio.com (sem espaços, sem pontos duplicados)."""
    email = (email or "").strip()
    if not email or len(email) > 254 or _EMAIL.fullmatch(email) is None:
        return False
    local = email.split("@", 1)[0]
    return len(local) <= 64 and not local.startswith(".") and not local.endswith(".") \
        and ".." not in email


# ------------------------------------------------- busca sem acento / valores
def normalizar(texto):
    """Minúsculas e sem acentos, para buscar ('joao' encontra 'João')."""
    base = unicodedata.normalize("NFD", (texto or "").casefold())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def brl(centavos):
    """12345 -> 'R$ 123,45' (só para exibição)."""
    centavos = int(centavos or 0)
    reais, resto = divmod(abs(centavos), 100)
    texto = f"{reais:,}".replace(",", ".") + f",{resto:02d}"
    return f"{'-' if centavos < 0 else ''}R$ {texto}"


VALOR_MAXIMO_CENTAVOS = 100_000_000  # R$ 1.000.000,00 (trava contra erro de digitação)


def valor_para_centavos(texto):
    """'150', '150,50', '1.234,56' ou 'R$ 150,00' -> centavos (int). Levanta ErroValidacao."""
    bruto = (texto or "").replace("R$", "").replace(" ", "").strip()
    mensagem = "Valor inválido. Digite um valor em reais, por exemplo 150,00."
    if not bruto:
        raise ErroValidacao(mensagem)
    if "," in bruto:  # formato brasileiro: ponto separa milhar, vírgula separa centavos
        bruto = bruto.replace(".", "").replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", bruto):
        raise ErroValidacao(mensagem)
    reais, _, cent = bruto.partition(".")
    centavos = int(reais) * 100 + int((cent + "0")[:2] if cent else 0)
    if centavos > VALOR_MAXIMO_CENTAVOS:
        raise ErroValidacao("Valor muito alto. Confira o valor digitado.")
    return centavos


def centavos_para_campo(centavos):
    """12345 -> '123,45' (para preencher um campo de edição)."""
    return f"{int(centavos or 0) // 100},{int(centavos or 0) % 100:02d}"


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


# ----------------------------------------------------------------- horários
def mascara_hora(texto):
    """Digitou 0930 -> 09:30 (usado enquanto o usuário digita)."""
    d = somente_digitos(texto)[:4]
    if len(d) <= 2:
        return d
    return f"{d[:2]}:{d[2:]}"


def hora_valida(texto):
    """Confere se o texto está no formato HH:MM (00:00 a 23:59)."""
    texto = (texto or "").strip()
    return bool(re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", texto))


def calcular_hora_fim(hora_inicio, duracao_minutos=30):
    """Calcula o horário de término (padrão: 30 minutos depois)."""
    if not hora_valida(hora_inicio):
        return hora_inicio
    horas, minutos = map(int, hora_inicio.split(":"))
    total_min = horas * 60 + minutos + duracao_minutos
    return f"{(total_min // 60) % 24:02d}:{total_min % 60:02d}"


def validar_data_hora_futura(data_br, hora_str):
    """Verifica se data e horário não estão no passado (RN05)."""
    data_obj = data_br_para_date(data_br)
    if not hora_valida(hora_str):
        raise ErroValidacao("Horário inválido. Use o formato HH:MM, por exemplo 09:30.")
    h, m = map(int, hora_str.split(":"))
    agendamento = datetime.combine(data_obj, datetime.min.time()).replace(hour=h, minute=m)
    if agendamento < datetime.now():
        raise ErroValidacao("Não é permitido agendar consultas em data e hora passadas.")

