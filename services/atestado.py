"""Atestado médico para impressão (folha A4).

Os dados do paciente e do médico vêm da consulta e são preenchidos sozinhos. Quem emite
digita apenas a quantidade de dias de afastamento, o CID (opcional) e, se quiser, o local
de emissão. O atestado sai com data de emissão, CRM/registro do médico e linha de assinatura.

Como o comprovante, é uma página HTML aberta no navegador já com a janela de impressão
(basta escolher a impressora ou "Salvar como PDF"). Este módulo não usa a interface gráfica.
"""
import html
import re
import tempfile
import webbrowser
from datetime import date
from pathlib import Path

from services import consultas, documentos
from services.validacoes import ErroValidacao, formatar_cpf, iso_para_data_br

NOME_CLINICA = "Sistema de Clínica"
LOCAL_PADRAO = "Cidade - UF"  # troque em ui/tema.py (LOCAL_EMISSAO)
MAXIMO_DIAS = 365

MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def validar_dias(dias):
    """Quantidade de dias: número inteiro de 1 a 365. Devolve o inteiro."""
    texto = str(dias if dias is not None else "").strip()
    if not re.fullmatch(r"\d{1,3}", texto) or not 1 <= int(texto) <= MAXIMO_DIAS:
        raise ErroValidacao(f"Informe a quantidade de dias (um número de 1 a {MAXIMO_DIAS}).")
    return int(texto)


def validar_cid(cid):
    """CID opcional no formato J11 ou J11.1 (letra + 2 números, ponto e até 2 dígitos)."""
    texto = (cid or "").strip().upper()
    if not texto:
        return ""
    if not re.fullmatch(r"[A-Z]\d{2}(\.\d{1,2})?", texto):
        raise ErroValidacao("CID inválido. Use o formato J11 ou J11.1 (letra + 2 números).")
    return texto


def _dias_por_extenso(n):
    return f"{n} dia" if n == 1 else f"{n} dias"


def data_por_extenso(data):
    """date(2026, 10, 21) -> '21 de outubro de 2026'."""
    return f"{data.day} de {MESES[data.month - 1]} de {data.year}"


def dados_do_atestado(id_consulta, dias, cid="", local="", clinica=NOME_CLINICA, hoje=None):
    """Junta os dados da consulta (paciente e médico) com os campos digitados."""
    dias = validar_dias(dias)
    cid = validar_cid(cid)
    c = consultas.obter(id_consulta)
    if not c:
        raise ErroValidacao("Consulta não encontrada.")
    if c["situacao"] == "Cancelada":
        raise ErroValidacao("Não é possível emitir atestado de uma consulta cancelada.")
    hoje = hoje or date.today()
    return {
        "clinica": clinica,
        "paciente": c["paciente_nome"],
        "cpf": formatar_cpf(c["paciente_cpf"]),
        "nascimento": iso_para_data_br(c["paciente_nascimento"]),
        "profissional": c["profissional_nome"],
        "registro": c["profissional_registro"],
        "especialidade": c["especialidade_nome"],
        "data_consulta": iso_para_data_br(c["data"]),
        "dias": dias,
        "cid": cid,
        "local": (local or "").strip() or LOCAL_PADRAO,
        "emissao": data_por_extenso(hoje),
    }


def gerar_texto(d):
    """Texto do atestado (serve para testes e para conferir o conteúdo)."""
    linhas = [
        d["clinica"].upper(),
        "ATESTADO MÉDICO",
        "",
        f"Atesto, para os devidos fins, que {d['paciente']}, CPF {d['cpf']}, "
        f"nascido(a) em {d['nascimento']}, foi atendido(a) em consulta no dia "
        f"{d['data_consulta']} e necessita de afastamento de suas atividades "
        f"por {_dias_por_extenso(d['dias'])}, a contar desta data.",
    ]
    if d["cid"]:
        linhas.append(f"CID: {d['cid']}")
    linhas += [
        "",
        f"{d['local']}, {d['emissao']}.",
        "",
        "______________________________________",
        d["profissional"],
        f"{d['registro']} - {d['especialidade']}",
    ]
    return "\n".join(linhas) + "\n"


def gerar_html(d):
    """Página HTML (A4) do atestado. Abre a janela de impressão sozinha."""
    e = html.escape
    cid = f"<p class='cid'><b>CID:</b> {e(d['cid'])}</p>" if d["cid"] else ""
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Atestado médico - {e(d['paciente'])}</title>
<style>
  @page {{ size: A4; margin: 25mm 20mm; }}
  body {{ font-family: "Times New Roman", serif; font-size: 14pt; color: #000; line-height: 1.6; }}
  h1 {{ font-size: 16pt; text-align: center; margin: 0; letter-spacing: 1px; }}
  h2 {{ font-size: 20pt; text-align: center; margin: 28mm 0 14mm; letter-spacing: 3px; }}
  p {{ text-align: justify; margin: 0 0 8mm; }}
  .cid {{ text-align: left; }}
  .local {{ margin-top: 14mm; text-align: right; }}
  .assinatura {{ margin: 28mm auto 0; width: 95mm; text-align: center; }}
  .assinatura .linha {{ border-top: 1px solid #000; padding-top: 2mm; }}
  .assinatura .reg {{ font-size: 12pt; }}
</style></head>
<body onload="window.print()">
  <h1>{e(d['clinica'])}</h1>
  <h2>ATESTADO MÉDICO</h2>
  <p>Atesto, para os devidos fins, que <b>{e(d['paciente'])}</b>, CPF {e(d['cpf'])},
  nascido(a) em {e(d['nascimento'])}, foi atendido(a) em consulta no dia
  {e(d['data_consulta'])} e necessita de afastamento de suas atividades por
  <b>{e(_dias_por_extenso(d['dias']))}</b>, a contar desta data.</p>
  {cid}
  <p class="local">{e(d['local'])}, {e(d['emissao'])}.</p>
  <div class="assinatura">
    <div class="linha"><b>{e(d['profissional'])}</b></div>
    <div class="reg">{e(d['registro'])} - {e(d['especialidade'])}</div>
  </div>
</body></html>
"""


def imprimir(id_consulta, dias, cid="", local="", clinica=NOME_CLINICA, usuario=None):
    """Gera o atestado, SALVA no banco (por paciente) e abre no navegador. Devolve o arquivo."""
    dados = dados_do_atestado(id_consulta, dias, cid, local, clinica)
    documentos.salvar(documentos.ATESTADO, id_consulta, gerar_texto(dados), gerar_html(dados), usuario)
    pasta = Path(tempfile.gettempdir()) / "sistema_clinica_atestados"
    pasta.mkdir(exist_ok=True)
    arquivo = pasta / f"atestado_{id_consulta:06d}.html"
    arquivo.write_text(gerar_html(dados), encoding="utf-8")
    if not webbrowser.open(arquivo.as_uri()):
        raise ErroValidacao(f"Não foi possível abrir o navegador. Abra o arquivo: {arquivo}")
    return arquivo
