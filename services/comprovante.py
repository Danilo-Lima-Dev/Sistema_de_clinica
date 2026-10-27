"""Comprovante de agendamento para impressora térmica (bobina).

Monta o comprovante de uma consulta em dois formatos:
  * texto simples (`gerar_texto`) - serve para testes, para salvar em .txt ou para
    enviar direto a uma impressora que aceite texto;
  * página HTML (`gerar_html`) - com tamanho de papel de bobina (80 mm ou 58 mm).
    É aberta no navegador já com a janela de impressão: basta escolher a impressora
    térmica. Funciona em Windows, Linux e macOS sem instalar nada.

Este módulo não usa a interface gráfica; a tela só chama `imprimir`.
"""
import html
import tempfile
import webbrowser
from datetime import datetime
from pathlib import Path

from services import consultas
from services.validacoes import (
    ErroValidacao,
    brl,
    formatar_telefone,
    iso_para_data_br,
    somente_digitos,
)

# largura do papel (mm) -> quantidade de caracteres por linha na versão texto
LARGURAS = {80: 42, 58: 32}
NOME_CLINICA = "Sistema de Clínica"


def mascarar_cpf(cpf):
    """Mostra só os 3 primeiros e os 2 últimos dígitos (LGPD): '52998224725' -> '529.***.***-25'."""
    d = somente_digitos(cpf)
    if len(d) != 11:
        return "***.***.***-**"
    return f"{d[:3]}.***.***-{d[9:]}"


def dados_do_comprovante(id_consulta, clinica=NOME_CLINICA):
    """Busca a consulta e devolve só o que vai impresso, já formatado."""
    c = consultas.obter(id_consulta)
    if not c:
        raise ErroValidacao("Consulta não encontrada.")
    return {
        "clinica": clinica,
        "numero": f"{c['id']:06d}",
        "paciente": c["paciente_nome"],
        "cpf": mascarar_cpf(c["paciente_cpf"]),
        "telefone": formatar_telefone(c["paciente_telefone"]) if c["paciente_telefone"] else "",
        "profissional": c["profissional_nome"],
        "registro": c["profissional_registro"],
        "especialidade": c["especialidade_nome"],
        "data": iso_para_data_br(c["data"]),
        "hora": c["hora_inicio"],
        "hora_fim": c["hora_fim"],
        "situacao": c["situacao"],
        # vem do registro financeiro da consulta: "Pago" ou "Aguardando pagamento"
        "pagamento": c["pagamento_status"],
        "valor": brl(c["valor_centavos"]),
        "observacoes": c["observacoes"] or "",
        "emitido_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


def _quebrar(texto, largura):
    """Quebra um texto longo em linhas de, no máximo, `largura` caracteres."""
    linhas, atual = [], ""
    for palavra in texto.split():
        while len(palavra) > largura:  # palavra maior que a linha
            if atual:
                linhas.append(atual)
                atual = ""
            linhas.append(palavra[:largura])
            palavra = palavra[largura:]
        if len(atual) + len(palavra) + (1 if atual else 0) > largura:
            linhas.append(atual)
            atual = palavra
        else:
            atual = f"{atual} {palavra}".strip()
    if atual:
        linhas.append(atual)
    return linhas or [""]


def gerar_texto(d, largura_mm=80):
    """Comprovante em texto puro, centralizado para a largura da bobina."""
    n = LARGURAS.get(largura_mm, LARGURAS[80])
    sep = "-" * n
    linhas = [d.get("clinica", NOME_CLINICA).center(n), "COMPROVANTE DE AGENDAMENTO".center(n), sep]

    def campo(rotulo, valor):
        if valor:
            linhas.extend(_quebrar(f"{rotulo}: {valor}", n))

    campo("Comprovante n.", d["numero"])
    linhas.append(sep)
    linhas.append("PACIENTE")
    campo("Nome", d["paciente"])
    campo("CPF", d["cpf"])
    campo("Telefone", d["telefone"])
    linhas.append(sep)
    linhas.append("PROFISSIONAL")
    campo("Nome", d["profissional"])
    campo("Registro", d["registro"])
    campo("Especialidade", d["especialidade"])
    linhas.append(sep)
    linhas.append("CONSULTA")
    campo("Data", d["data"])
    campo("Horario", f"{d['hora']} as {d['hora_fim']}")
    campo("Situacao", d["situacao"])
    campo("Valor", d["valor"])
    campo("Pagamento", d["pagamento"].upper())
    campo("Obs", d["observacoes"])
    linhas.append(sep)
    linhas.extend(_quebrar("Chegue com 15 minutos de antecedencia e guarde este comprovante.", n))
    linhas.append(sep)
    linhas.append(f"Emitido em {d['emitido_em']}".center(n))
    return "\n".join(linhas) + "\n"


def gerar_html(d, largura_mm=80):
    """Página HTML com a largura útil da bobina. Abre a janela de impressão sozinha."""
    e = html.escape
    fonte = "11pt" if largura_mm >= 80 else "9pt"

    def bloco(titulo, itens):
        linhas = "".join(
            f"<div><b>{e(r)}:</b> {e(v)}</div>" for r, v in itens if v
        )
        return f"<h2>{e(titulo)}</h2>{linhas}<hr>"

    corpo = (
        f"<h1>{e(d.get('clinica', NOME_CLINICA))}</h1><p class='c'><b>COMPROVANTE DE AGENDAMENTO</b></p><hr>"
        f"<div><b>Comprovante n.:</b> {e(d['numero'])}</div><hr>"
        + bloco("PACIENTE", [("Nome", d["paciente"]), ("CPF", d["cpf"]), ("Telefone", d["telefone"])])
        + bloco("PROFISSIONAL", [("Nome", d["profissional"]), ("Registro", d["registro"]),
                                 ("Especialidade", d["especialidade"])])
        + bloco("CONSULTA", [("Data", d["data"]), ("Horário", f"{d['hora']} às {d['hora_fim']}"),
                             ("Situação", d["situacao"]), ("Valor", d["valor"]),
                             ("Pagamento", d["pagamento"].upper()), ("Obs", d["observacoes"])])
        + "<p class='c'>Chegue com 15 minutos de antecedência e guarde este comprovante.</p><hr>"
        + f"<p class='c pequeno'>Emitido em {e(d['emitido_em'])}</p>"
    )
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Comprovante {e(d['numero'])}</title>
<style>
  /* O papel (80 ou 58 mm) é o da impressora escolhida; aqui só limitamos a largura útil. */
  @page {{ margin: 2mm; }}
  body {{ width: {largura_mm - 8}mm; margin: 0 auto; font-family: "Courier New", monospace;
          font-size: {fonte}; color: #000; }}
  h1 {{ font-size: 13pt; text-align: center; margin: 2mm 0; }}
  h2 {{ font-size: {fonte}; margin: 1mm 0; }}
  hr {{ border: 0; border-top: 1px dashed #000; margin: 2mm 0; }}
  div, p {{ margin: 0.5mm 0; word-wrap: break-word; }}
  .c {{ text-align: center; }}
  .pequeno {{ font-size: 8pt; }}
</style></head>
<body onload="window.print()">{corpo}</body></html>
"""


def imprimir(id_consulta, largura_mm=80, clinica=NOME_CLINICA):
    """Gera o comprovante e abre no navegador (com a janela de impressão).

    Devolve o caminho do arquivo HTML criado.
    """
    dados = dados_do_comprovante(id_consulta, clinica)
    pasta = Path(tempfile.gettempdir()) / "sistema_clinica_comprovantes"
    pasta.mkdir(exist_ok=True)
    arquivo = pasta / f"comprovante_{dados['numero']}.html"
    arquivo.write_text(gerar_html(dados, largura_mm), encoding="utf-8")
    if not webbrowser.open(arquivo.as_uri()):
        raise ErroValidacao(f"Não foi possível abrir o navegador. Abra o arquivo: {arquivo}")
    return arquivo
