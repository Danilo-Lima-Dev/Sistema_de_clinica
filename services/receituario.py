"""Receituário médico para impressão (folha A4).

Os dados do paciente e do médico vêm da consulta selecionada e são preenchidos sozinhos.
Quem emite digita só a prescrição (medicamentos, doses e orientações) e, se quiser, o local.
Sai com data de emissão, CRM/registro do médico e linha de assinatura.

Como o comprovante e o atestado, é uma página HTML aberta no navegador já com a janela de
impressão (escolha a impressora ou "Salvar como PDF"). Não usa a interface gráfica.
"""
import html
import tempfile
import webbrowser
from datetime import date
from pathlib import Path

from services import consultas, documentos
from services.atestado import LOCAL_PADRAO, NOME_CLINICA, data_por_extenso
from services.validacoes import ErroValidacao, formatar_cpf, iso_para_data_br

MAXIMO_CARACTERES = 4000


def validar_prescricao(texto):
    """A prescrição é obrigatória. Mantém as quebras de linha digitadas."""
    texto = (texto or "").strip()
    if not texto:
        raise ErroValidacao("Digite a prescrição (medicamentos, doses e orientações).")
    if len(texto) > MAXIMO_CARACTERES:
        raise ErroValidacao(f"Prescrição muito longa (máximo {MAXIMO_CARACTERES} caracteres).")
    return texto


def dados_do_receituario(id_consulta, prescricao, local="", clinica=NOME_CLINICA, hoje=None):
    """Junta os dados da consulta (paciente e médico) com a prescrição digitada."""
    prescricao = validar_prescricao(prescricao)
    c = consultas.obter(id_consulta)
    if not c:
        raise ErroValidacao("Consulta não encontrada.")
    if c["situacao"] == "Cancelada":
        raise ErroValidacao("Não é possível emitir receituário de uma consulta cancelada.")
    return {
        "clinica": clinica,
        "paciente": c["paciente_nome"],
        "cpf": formatar_cpf(c["paciente_cpf"]),
        "nascimento": iso_para_data_br(c["paciente_nascimento"]),
        "profissional": c["profissional_nome"],
        "registro": c["profissional_registro"],
        "especialidade": c["especialidade_nome"],
        "prescricao": prescricao,
        "local": (local or "").strip() or LOCAL_PADRAO,
        "emissao": data_por_extenso(hoje or date.today()),
    }


def gerar_texto(d):
    """Texto do receituário (serve para testes e para conferir o conteúdo)."""
    linhas = [
        d["clinica"].upper(), "RECEITUÁRIO MÉDICO", "",
        f"Paciente: {d['paciente']}",
        f"CPF: {d['cpf']}    Nascimento: {d['nascimento']}", "",
        "Prescrição:", d["prescricao"], "",
        f"{d['local']}, {d['emissao']}.", "",
        "______________________________________",
        d["profissional"], f"{d['registro']} - {d['especialidade']}",
    ]
    return "\n".join(linhas) + "\n"


def gerar_html(d):
    """Página HTML (A4) do receituário. Abre a janela de impressão sozinha."""
    e = html.escape
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Receituário - {e(d['paciente'])}</title>
<style>
  @page {{ size: A4; margin: 20mm; }}
  body {{ font-family: "Times New Roman", serif; font-size: 13pt; color: #000; line-height: 1.5; }}
  h1 {{ font-size: 16pt; text-align: center; margin: 0; letter-spacing: 1px; }}
  h2 {{ font-size: 18pt; text-align: center; margin: 10mm 0 8mm; letter-spacing: 3px; }}
  .paciente {{ border: 1px solid #000; padding: 3mm 4mm; margin-bottom: 8mm; }}
  .rotulo {{ font-weight: bold; margin-bottom: 3mm; }}
  .prescricao {{ white-space: pre-wrap; min-height: 90mm; }}
  .local {{ margin-top: 10mm; text-align: right; }}
  .assinatura {{ margin: 22mm auto 0; width: 95mm; text-align: center; }}
  .assinatura .linha {{ border-top: 1px solid #000; padding-top: 2mm; }}
  .assinatura .reg {{ font-size: 11pt; }}
</style></head>
<body onload="window.print()">
  <h1>{e(d['clinica'])}</h1>
  <h2>RECEITUÁRIO MÉDICO</h2>
  <div class="paciente"><b>Paciente:</b> {e(d['paciente'])}<br>
  <b>CPF:</b> {e(d['cpf'])} &nbsp;&nbsp; <b>Nascimento:</b> {e(d['nascimento'])}</div>
  <div class="rotulo">Prescrição:</div>
  <div class="prescricao">{e(d['prescricao'])}</div>
  <p class="local">{e(d['local'])}, {e(d['emissao'])}.</p>
  <div class="assinatura">
    <div class="linha"><b>{e(d['profissional'])}</b></div>
    <div class="reg">{e(d['registro'])} - {e(d['especialidade'])}</div>
  </div>
</body></html>
"""


def imprimir(id_consulta, prescricao, local="", clinica=NOME_CLINICA, usuario=None):
    """Gera o receituário, SALVA no banco (por paciente) e abre no navegador. Devolve o arquivo."""
    dados = dados_do_receituario(id_consulta, prescricao, local, clinica)
    documentos.salvar(
        documentos.RECEITUARIO, id_consulta, gerar_texto(dados), gerar_html(dados), usuario
    )
    pasta = Path(tempfile.gettempdir()) / "sistema_clinica_receituarios"
    pasta.mkdir(exist_ok=True)
    arquivo = pasta / f"receituario_{id_consulta:06d}.html"
    arquivo.write_text(gerar_html(dados), encoding="utf-8")
    if not webbrowser.open(arquivo.as_uri()):
        raise ErroValidacao(f"Não foi possível abrir o navegador. Abra o arquivo: {arquivo}")
    return arquivo
