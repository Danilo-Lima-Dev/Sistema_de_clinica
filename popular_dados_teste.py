"""Popula o banco com DADOS FICTÍCIOS para teste e demonstração.

Uso (na pasta do projeto):   python popular_dados_teste.py
Para começar de um banco limpo, feche o sistema e apague o clinica.db antes.

Todos os nomes, CPFs, telefones e e-mails abaixo são inventados (CPFs gerados só para teste,
e-mails @exemplo.com). Não rode isto num banco com dados reais.

Logins criados (senha entre parênteses):
  super (super123)                          -> Administrador
  admin (admin123), recepcao (recepcao123)  -> Atendente (recepção)
  helena, rafael, luiza (medico123)         -> Médico (Pediatria, Cardiologia, Dermatologia)
"""
from datetime import date, timedelta
from unittest import mock

import database
from services import (
    agenda, atestado, autenticacao, consultas, documentos, especialidades, financeiro,
    historico_clinico, pacientes, profissionais, receituario,
)
from services.autenticacao import PAPEL_ATENDENTE, PAPEL_MEDICO


def cpf_ficticio(base9):
    """Completa 9 dígitos com os 2 dígitos verificadores (CPF só para teste)."""
    d = [int(c) for c in base9]
    for n in (9, 10):
        d.append((sum(d[i] * (n + 1 - i) for i in range(n)) * 10) % 11 % 10)
    return "".join(map(str, d))


def dia_util(deslocamento):
    """Dia útil mais próximo, `deslocamento` dias a partir de hoje (negativo = passado)."""
    d = date.today() + timedelta(days=deslocamento)
    passo = 1 if deslocamento >= 0 else -1
    while d.weekday() > 4:
        d += timedelta(days=passo)
    return d.strftime("%d/%m/%Y")


def main():
    database.criar_tabelas()
    autenticacao.criar_usuario_padrao()
    autenticacao.criar_superusuario_padrao()
    if any(p["nome"] == "Maria das Dores Silva" for p in pacientes.listar()):
        print("Os dados de teste já foram carregados neste banco. Nada a fazer.")
        return
    sup = autenticacao.autenticar("super", "super123")  # Administrador

    # --- valores das especialidades (só o Administrador altera)
    for nome, valor in (("Clínica Geral", 15000), ("Pediatria", 18000), ("Cardiologia", 25000),
                        ("Dermatologia", 22000), ("Ortopedia", 23000)):
        esp = next(e for e in especialidades.listar() if e["nome"] == nome)
        financeiro.alterar_valor_especialidade(sup["id"], esp["id"], valor)

    # --- profissionais
    prof = {}
    for chave, nome, reg, esp, tel in (
        ("helena", "Dra. Helena Duarte", "CRM-PI 2002", "Pediatria", "86982341234"),
        ("rafael", "Dr. Rafael Nogueira", "CRM-PI 1001", "Cardiologia", "86991234567"),
        ("luiza", "Dra. Luiza Menezes", "CRM-PI 3003", "Dermatologia", "86988873201"),
        ("caio", "Dr. Caio Ferraz", "CRM-PI 4004", "Ortopedia", "86981552545"),
        ("sonia", "Dra. Sônia Brandão", "CRM-PI 5005", "Clínica Geral", "86994393542"),
    ):
        prof[chave] = profissionais.cadastrar(nome, reg, esp, tel)
    profissionais.alternar_ativo(prof["sonia"])  # exemplo de profissional inativo

    # --- usuários (Médico ligado a um profissional; Atendente sem vínculo)
    for nome, login, chave in (("Dra. Helena Duarte", "helena", "helena"),
                               ("Dr. Rafael Nogueira", "rafael", "rafael"),
                               ("Dra. Luiza Menezes", "luiza", "luiza")):
        autenticacao.cadastrar_usuario_por(
            sup["id"], nome, login, "medico123", papel=PAPEL_MEDICO, profissional_id=prof[chave])
    autenticacao.cadastrar_usuario_por(
        sup["id"], "Camila Recepção", "recepcao", "recepcao123", papel=PAPEL_ATENDENTE)
    medico = {c: autenticacao.autenticar(c, "medico123") for c in ("helena", "rafael", "luiza")}
    recepcao = autenticacao.autenticar("recepcao", "recepcao123")

    # --- pacientes
    P = {}
    lista = (
        ("Maria das Dores Silva", "12/03/1978", "86982341234", "maria.dores@exemplo.com"),
        ("João Pedro Almeida", "05/11/1990", "86991234567", "joao.almeida@exemplo.com"),
        ("Ana Beatriz Costa", "23/07/1985", "86988887777", "ana.costa@exemplo.com"),
        ("Carlos Eduardo Rocha", "30/01/1969", "86981552545", ""),
        ("Francisca Araújo", "17/09/2001", "86994393542", "francisca@exemplo.com"),
        ("Pedro Henrique Lima", "02/06/2015", "86982215566", "responsavel.pedro@exemplo.com"),
        ("Luciana Martins", "14/12/1992", "86999413322", "luciana.m@exemplo.com"),
        ("Antônio Carlos Pereira", "08/04/1955", "8632218899", ""),
        ("Beatriz Souza Oliveira", "21/08/2008", "86988142277", "bia.souza@exemplo.com"),
        ("Rafaela Mendes", "11/02/1998", "86981349966", "rafaela.m@exemplo.com"),
        ("Gabriel Santos", "29/10/1987", "86992648817", "gabriel.s@exemplo.com"),
        ("Helena Ribeiro", "03/05/1973", "86983946120", "helena.r@exemplo.com"),
    )
    for i, (nome, nasc, tel, email) in enumerate(lista):
        P[nome.split()[0]] = pacientes.cadastrar(nome, cpf_ficticio(f"{100200301 + i * 7919:09d}"), nasc, tel, email)
    pacientes.alternar_ativo(P["Carlos"])  # exemplo de paciente desativado

    # --- consultas: passado (realizadas/canceladas), hoje/futuro (agendadas, pagas, confirmadas)
    hoje, amanha, d2, d3, d5 = dia_util(0), dia_util(1), dia_util(2), dia_util(3), dia_util(5)
    p1, p2, p3 = dia_util(-3), dia_util(-6), dia_util(-9)
    c = {}

    def marcar(chave, pac, med, data, hora, obs, futuro=True):
        c[chave] = consultas.agendar(P[pac], prof[med], data, hora, obs, validar_futuro=futuro)

    def pagar(*chaves):
        for k in chaves:  # pagamento e confirmação: feitos pela recepção
            financeiro.registrar_pagamento(recepcao["id"], c[k])

    def confirmar(*chaves):
        for k in chaves:
            consultas.confirmar(recepcao["id"], c[k])

    marcar("h1", "Maria", "helena", p1, "09:00", "Revisão", futuro=False)
    marcar("h2", "Pedro", "helena", p2, "10:30", "Febre há 3 dias", futuro=False)
    marcar("h3", "Luciana", "luiza", p3, "14:00", "Manchas na pele", futuro=False)
    marcar("h4", "Antônio", "rafael", p2, "08:30", "Controle de pressão", futuro=False)
    marcar("h5", "Gabriel", "caio", p3, "16:00", "Dor no joelho", futuro=False)
    pagar("h1", "h2", "h3", "h4", "h5"); confirmar("h1", "h2", "h3", "h4", "h5")
    donos = {"h1": "helena", "h2": "helena", "h3": "luiza", "h4": "rafael"}
    for k, dono in donos.items():  # só o médico da consulta marca como realizada
        consultas.marcar_realizada(medico[dono]["id"], c[k])
    marcar("x1", "Francisca", "luiza", p1, "11:00", "Avaliação", futuro=False)
    consultas.cancelar(c["x1"], "Paciente avisou que não poderá comparecer")

    marcar("a2", "Ana", "helena", amanha, "10:30", "Consulta de rotina")
    marcar("a3", "João", "rafael", amanha, "09:30", "Retorno")
    marcar("a4", "Beatriz", "helena", amanha, "09:00", "Vacinação")
    marcar("a5", "Rafaela", "luiza", d2, "14:00", "Avaliação de pele")
    marcar("a6", "Helena", "rafael", d2, "08:30", "Exame de rotina")
    marcar("a7", "Gabriel", "caio", d3, "15:00", "Retorno ortopédico")
    marcar("a8", "Antônio", "rafael", d3, "11:00", "Eletrocardiograma")
    marcar("a9", "Luciana", "luiza", d5, "10:00", "Acompanhamento")
    pagar("a3", "a4", "a6", "a7"); confirmar("a3", "a4", "a6")  # a7 paga e ainda não confirmada
    marcar("x2", "Ana", "rafael", d5, "16:00", "Dor no peito")
    pagar("x2"); consultas.cancelar(c["x2"], "Remarcada pelo paciente")

    # --- agenda: almoço bloqueado de uma médica no dia de amanhã
    dia_iso = "-".join(reversed(amanha.split("/")))  # a agenda recebe AAAA-MM-DD
    agenda.bloquear_horario(prof["helena"], dia_iso, "12:00", "Almoço")
    agenda.bloquear_horario(prof["helena"], dia_iso, "12:30", "Almoço")

    # --- documentos emitidos (só o médico responsável emite)
    with mock.patch("webbrowser.open", return_value=True):
        atestado.imprimir(c["h1"], "2", "J11", "Teresina - PI", usuario=medico["helena"])
        receituario.imprimir(c["h2"], "1) Dipirona gotas - 20 gotas a cada 6 horas por 3 dias\n"
                             "2) Repouso e hidratação", "Teresina - PI", usuario=medico["helena"])
        receituario.imprimir(c["h4"], "1) Losartana 50 mg - 1 comprimido pela manhã, uso contínuo",
                             "Teresina - PI", usuario=medico["rafael"])

    # --- 2ª via de um atestado, entregue pela recepção (fica no registro de entregas)
    pac_maria = P["Maria"]
    id_atestado = documentos.listar(recepcao["id"], pac_maria)[0]["id"]
    with mock.patch("webbrowser.open", return_value=True):
        documentos.entregar_segunda_via(
            recepcao["id"], id_atestado, "Impressão", "Maria das Dores Silva",
            "Próprio paciente", "529.982.247-25",
        )

    # --- histórico clínico (só médicos escrevem)
    historico_clinico.adicionar(medico["helena"]["id"], P["Maria"],
                                "Retorno de rotina. Sem queixas novas. Mantida a conduta anterior.", c["h1"])
    historico_clinico.adicionar(medico["helena"]["id"], P["Pedro"],
                                "Febre há 3 dias, sem outros sintomas. Orofaringe hiperemiada. "
                                "Conduta: sintomáticos e retorno em 5 dias se persistir.", c["h2"])
    id_h = historico_clinico.adicionar(medico["rafael"]["id"], P["Antônio"],
                                       "Hipertenso. PA 150x95. Iniciada losartana 50 mg.", c["h4"])
    historico_clinico.alterar(medico["rafael"]["id"], id_h,
                              "Hipertenso. PA 150x95. Iniciada losartana 50 mg. Retorno em 30 dias com exames.")
    historico_clinico.adicionar(medico["luiza"]["id"], P["Luciana"],
                                "Dermatite de contato em antebraço. Prescrito corticoide tópico.", c["h3"])

    print("Dados de teste carregados.")
    print("Logins: super/super123 (Administrador); admin/admin123 e recepcao/recepcao123 (Atendente);"
          " helena, rafael, luiza / medico123 (Médico)")


if __name__ == "__main__":
    main()
