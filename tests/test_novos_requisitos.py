"""Testes dos 11 requisitos novos. Execute com:  python -m unittest discover -s tests -v"""
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
from services import (  # noqa: E402
    agenda, atestado, autenticacao, comprovante, consultas, documentos, especialidades,
    financeiro, pacientes, profissionais, receituario,
)
from services.validacoes import (  # noqa: E402
    ErroValidacao, brl, email_valido, mascara_telefone, motivo_telefone_invalido,
    normalizar, valor_para_centavos,
)

CPF_1, CPF_2 = "52998224725", "11144477735"


def proximo_dia_util(dias=3):
    d = date.today() + timedelta(days=dias)
    while d.weekday() > 4:
        d += timedelta(days=1)
    return d


class Base(unittest.TestCase):
    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._pasta.name) / "t.db"
        database.criar_tabelas()
        autenticacao.criar_usuario_padrao()
        autenticacao.criar_superusuario_padrao()
        self.super = autenticacao.autenticar("super", autenticacao.SUPER_SENHA)
        self.comum = autenticacao.autenticar("admin", autenticacao.SENHA_PADRAO)
        self.pac = pacientes.cadastrar("João Silva", CPF_1, "01/01/1990", "86982341234", "j@x.com")
        self.prof = profissionais.cadastrar("Dra. Ana", "CRM 1", "Cardiologia")
        self.dia = proximo_dia_util()
        self.dia_br = self.dia.strftime("%d/%m/%Y")

    def tearDown(self):
        self._pasta.cleanup()

    def agendar(self, hora="09:00"):
        return consultas.agendar(self.pac, self.prof, self.dia_br, hora)


class TestTelefoneEmail(unittest.TestCase):  # itens 7 e 8
    def test_telefones_validos(self):
        for t in ("86982341234", "(11) 99999-8888", "8632211234"):
            self.assertIsNone(motivo_telefone_invalido(t), t)

    def test_telefones_invalidos(self):
        for t in ("12345678", "11000000000", "(11) 00000-0000", "11987654321", "1000000000",
                  "11 3333", "8699912345", "86 2222-2222"):
            self.assertIsNotNone(motivo_telefone_invalido(t), t)

    def test_mascara(self):
        self.assertEqual(mascara_telefone("86999998888"), "(86) 99999-8888")
        self.assertEqual(mascara_telefone("(86) 3221-12ab34"), "(86) 3221-1234")
        self.assertEqual(mascara_telefone(""), "")

    def test_email(self):
        for ok in ("a@b.com", "nome.sobrenome@dominio.com.br"):
            self.assertTrue(email_valido(ok), ok)
        for ruim in ("", "a", "a@b", "a@@b.com", "a b@c.com", "a..b@c.com", ".a@b.com", "a@b.c"):
            self.assertFalse(email_valido(ruim), ruim)

    def test_back_end_recusa(self):
        database.DB_PATH = Path(tempfile.mkdtemp()) / "x.db"
        database.criar_tabelas()
        with self.assertRaises(ErroValidacao):
            pacientes.cadastrar("Ana", CPF_1, "01/01/2000", telefone="12345678900")
        with self.assertRaises(ErroValidacao):
            pacientes.cadastrar("Ana", CPF_1, "01/01/2000", email="a@b")

    def test_busca_sem_acento_e_valores(self):
        self.assertEqual(normalizar("João"), "joao")
        self.assertEqual(valor_para_centavos("1.234,56"), 123456)
        self.assertEqual(brl(15000), "R$ 150,00")
        with self.assertRaises(ErroValidacao):
            valor_para_centavos("abc")


class TestValoresEFinanceiro(Base):  # itens 2, 4, 5, 3
    def test_valor_so_super(self):
        esp = especialidades.listar("cardio")[0]
        with self.assertRaises(ErroValidacao):
            financeiro.alterar_valor_especialidade(self.comum["id"], esp["id"], 15000)
        with self.assertRaises(ErroValidacao):
            especialidades.atualizar(esp["id"], esp["nome"], 15000, executor_id=self.comum["id"])
        financeiro.alterar_valor_especialidade(self.super["id"], esp["id"], 15000)
        self.assertEqual(especialidades.obter(esp["id"])["valor_consulta"], 15000)

    def test_financeiro_bloqueado_para_comum(self):
        for chamada in (
            lambda: financeiro.resumo(self.comum["id"]),
            lambda: financeiro.historico(self.comum["id"]),
            lambda: financeiro.listar_consultas(self.comum["id"]),
            lambda: financeiro.registrar_pagamento(self.comum["id"], 1),
        ):
            with self.assertRaises(ErroValidacao):
                chamada()

    def test_consulta_nasce_aguardando_com_valor_da_especialidade(self):
        esp = especialidades.listar("cardio")[0]
        financeiro.alterar_valor_especialidade(self.super["id"], esp["id"], 15000)
        c = consultas.obter(self.agendar())
        self.assertEqual(c["pagamento_status"], "Aguardando pagamento")
        self.assertEqual(c["valor_centavos"], 15000)

    def test_confirmar_so_apos_pagamento(self):
        id_c = self.agendar()
        with self.assertRaises(ErroValidacao):
            consultas.confirmar(id_c)
        financeiro.registrar_pagamento(self.super["id"], id_c)
        consultas.confirmar(id_c)
        self.assertEqual(consultas.obter(id_c)["situacao"], "Confirmada")
        with self.assertRaises(ErroValidacao):  # confirmada: não desfaz o pagamento
            financeiro.desfazer_pagamento(self.super["id"], id_c)

    def test_banco_tambem_recusa_confirmar_sem_pagamento(self):
        id_c = self.agendar()
        with self.assertRaises(sqlite3.IntegrityError):
            with database.transacao() as con:
                con.execute("UPDATE consulta SET situacao = 'Confirmada' WHERE id = ?", (id_c,))

    def test_painel_e_historico(self):
        a, b = self.agendar("09:00"), self.agendar("10:00")
        financeiro.alterar_valor_consulta(self.super["id"], a, 10000)
        financeiro.alterar_valor_consulta(self.super["id"], b, 5000)
        financeiro.registrar_pagamento(self.super["id"], a)
        r = financeiro.resumo(self.super["id"])
        self.assertEqual((r["recebido"], r["pendente"]), (10000, 5000))
        consultas.cancelar(b)
        self.assertEqual(financeiro.resumo(self.super["id"])["pendente"], 0)
        filtro = financeiro.resumo(self.super["id"], profissional_id=999)
        self.assertEqual(filtro["recebido"], 0)
        hist = financeiro.historico(self.super["id"])
        self.assertEqual(len(hist), 3)
        self.assertIn("Super", hist[0]["usuario_nome"])
        with self.assertRaises(ErroValidacao):  # consulta paga não muda de valor
            financeiro.alterar_valor_consulta(self.super["id"], a, 1)

    def test_comprovante_traz_status_de_pagamento(self):
        id_c = self.agendar()
        self.assertIn("AGUARDANDO PAGAMENTO", comprovante.gerar_texto(comprovante.dados_do_comprovante(id_c)))
        financeiro.registrar_pagamento(self.super["id"], id_c)
        dados = comprovante.dados_do_comprovante(id_c)
        self.assertEqual(dados["pagamento"], "Pago")
        self.assertIn("PAGO", comprovante.gerar_html(dados))


class TestAgenda(Base):  # item 1
    def estados(self):
        return {h["hora_inicio"]: h["estado"] for h in agenda.horarios_do_dia(self.prof, self.dia)}

    def test_tres_estados(self):
        self.agendar("09:00")
        agenda.bloquear_horario(self.prof, self.dia, "10:00", "Reunião")
        e = self.estados()
        self.assertEqual((e["08:00"], e["09:00"], e["10:00"]), ("disponivel", "reservado", "indisponivel"))

    def test_indisponivel_nao_aceita_agendamento(self):
        agenda.bloquear_horario(self.prof, self.dia, "10:00")
        with self.assertRaises(ErroValidacao):
            self.agendar("10:00")
        with self.assertRaises(ErroValidacao):  # fora do expediente
            self.agendar("19:00")
        sabado = self.dia + timedelta(days=(5 - self.dia.weekday()))
        with self.assertRaises(ErroValidacao):
            consultas.agendar(self.pac, self.prof, sabado.strftime("%d/%m/%Y"), "09:00")

    def test_liberar_e_bloquear_dia(self):
        self.agendar("09:00")
        with self.assertRaises(ErroValidacao):  # horário reservado não bloqueia
            agenda.bloquear_horario(self.prof, self.dia, "09:00")
        bloqueados, mantidos = agenda.bloquear_dia(self.prof, self.dia)
        self.assertEqual((bloqueados, mantidos), (19, 1))
        self.assertEqual(agenda.liberar_dia(self.prof, self.dia), 19)
        agenda.bloquear_horario(self.prof, self.dia, "11:00")
        agenda.liberar_horario(self.prof, self.dia, "11:00")
        with self.assertRaises(ErroValidacao):
            agenda.liberar_horario(self.prof, self.dia, "11:00")

    def test_cancelar_libera_horario(self):
        id_c = self.agendar("09:00")
        consultas.cancelar(id_c)
        self.assertEqual(self.estados()["09:00"], "disponivel")


class TestExclusoesEBuscas(Base):  # itens 9, 10, 11
    def test_especialidade_com_vinculo_nao_exclui(self):
        esp = especialidades.listar("cardio")[0]
        with self.assertRaises(ErroValidacao) as ctx:
            especialidades.excluir(esp["id"])
        self.assertIn("médico", str(ctx.exception))
        livre = especialidades.cadastrar("Neurologia")
        especialidades.excluir(livre)
        self.assertEqual(especialidades.listar("neuro"), [])

    def test_especialidade_so_com_consulta_tambem_bloqueia(self):
        self.agendar()
        esp = especialidades.listar("cardio")[0]
        with self.assertRaises(ErroValidacao) as ctx:
            especialidades.excluir(esp["id"])
        self.assertIn("consulta", str(ctx.exception))

    def test_paciente_com_consulta_desativa_em_vez_de_excluir(self):
        self.agendar()
        with self.assertRaises(ErroValidacao) as ctx:
            pacientes.excluir(self.pac)
        self.assertIn("Desativar", str(ctx.exception))
        self.assertEqual(pacientes.alternar_ativo(self.pac), 0)
        self.assertEqual(pacientes.listar("joao", incluir_inativos=False), [])
        self.assertEqual(len(pacientes.listar("joao")), 1)
        with self.assertRaises(ErroValidacao):  # desativado não agenda
            self.agendar("10:00")
        self.assertEqual(pacientes.alternar_ativo(self.pac), 1)
        self.agendar("10:00")

    def test_buscas_sem_acento_parcial_cpf_telefone(self):
        self.assertEqual(len(pacientes.listar("JOAO")), 1)
        self.assertEqual(len(pacientes.listar("ilva")), 1)
        self.assertEqual(len(pacientes.listar("86 98234")), 1)  # telefone
        self.assertEqual(len(pacientes.listar("529.982")), 1)   # CPF
        self.assertEqual(len(especialidades.listar("CARD")), 1)
        self.assertEqual(len(profissionais.listar("ana")), 1)
        self.assertEqual(len(profissionais.listar("cardio")), 1)  # por especialidade
        self.assertEqual(profissionais.listar("zzz"), [])

    def test_limite_para_autocompletar(self):
        for i in range(15):
            pacientes.cadastrar(f"Maria {i:02d}", f"{i:011d}", "01/01/2000")
        self.assertEqual(len(pacientes.listar("maria", limite=10)), 10)
        self.assertEqual(len(pacientes.listar("maria", limite=10, offset=10)), 5)


class TestAtestado(Base):  # item 6
    def test_dados_automaticos_e_manuais(self):
        id_c = self.agendar()
        d = atestado.dados_do_atestado(id_c, "3", "j11", "Teresina - PI", hoje=date(2026, 10, 21))
        texto = atestado.gerar_texto(d)
        for trecho in ("João Silva", "Dra. Ana", "CRM 1", "3 dias", "J11", "Teresina - PI",
                       "21 de outubro de 2026", "______"):
            self.assertIn(trecho, texto)
        self.assertIn("linha", atestado.gerar_html(d))

    def test_validacoes(self):
        id_c = self.agendar()
        for dias in ("", "0", "abc", "400"):
            with self.assertRaises(ErroValidacao):
                atestado.dados_do_atestado(id_c, dias)
        with self.assertRaises(ErroValidacao):
            atestado.dados_do_atestado(id_c, "2", "99X")
        consultas.cancelar(id_c)
        with self.assertRaises(ErroValidacao):
            atestado.dados_do_atestado(id_c, "2")


class TestReceituario(Base):
    def test_dados_automaticos_e_prescricao(self):
        id_c = self.agendar()
        d = receituario.dados_do_receituario(
            id_c, "1) Dipirona 500 mg\n2) Repouso", "Teresina - PI", hoje=date(2026, 10, 21)
        )
        texto = receituario.gerar_texto(d)
        for trecho in ("João Silva", "529.982.247-25", "Dra. Ana", "CRM 1", "Dipirona 500 mg",
                       "Repouso", "Teresina - PI", "21 de outubro de 2026", "______"):
            self.assertIn(trecho, texto)
        self.assertIn("pre-wrap", receituario.gerar_html(d))

    def test_validacoes(self):
        id_c = self.agendar()
        for ruim in ("", "   ", "x" * 4001):
            with self.assertRaises(ErroValidacao):
                receituario.dados_do_receituario(id_c, ruim)
        d = receituario.dados_do_receituario(id_c, "<b>x</b>")
        self.assertNotIn("<b>x</b>", receituario.gerar_html(d))  # texto digitado é escapado
        consultas.cancelar(id_c)
        with self.assertRaises(ErroValidacao):
            receituario.dados_do_receituario(id_c, "algo")


class TestDocumentosSalvos(Base):
    def emitir(self, id_c):
        with mock.patch("webbrowser.open", return_value=True):
            atestado.imprimir(id_c, "2", "J11", "Teresina - PI", usuario=self.comum)
            receituario.imprimir(id_c, "Dipirona 500 mg", "Teresina - PI", usuario=self.comum)

    def test_emitir_salva_no_banco_por_paciente(self):
        id_c = self.agendar()
        self.emitir(id_c)
        docs = documentos.listar(self.super["id"], self.pac)
        self.assertEqual(sorted(d["tipo"] for d in docs), ["Atestado", "Receituário"])
        self.assertEqual(docs[0]["emitido_por_nome"], self.comum["nome"])
        completo = documentos.obter(self.super["id"], docs[0]["id"])
        self.assertIn("João Silva", completo["texto"])
        self.assertIn("<html", completo["html"])
        outro = pacientes.cadastrar("Outro", CPF_2, "01/01/1980")
        self.assertEqual(documentos.listar(self.super["id"], outro), [])  # separado por paciente

    def test_so_super_usuario_ve(self):
        id_c = self.agendar()
        self.emitir(id_c)
        id_doc = documentos.listar(self.super["id"], self.pac)[0]["id"]
        for chamada in (
            lambda: documentos.listar(self.comum["id"], self.pac),
            lambda: documentos.obter(self.comum["id"], id_doc),
            lambda: documentos.reimprimir(self.comum["id"], id_doc),
            lambda: documentos.listar(None, self.pac),
        ):
            with self.assertRaises(ErroValidacao):
                chamada()
        with mock.patch("webbrowser.open", return_value=True):
            self.assertTrue(documentos.reimprimir(self.super["id"], id_doc).exists())

    def test_documento_invalido_nao_salva(self):
        id_c = self.agendar()
        with self.assertRaises(ErroValidacao):
            atestado.imprimir(id_c, "0")  # dias inválidos: nada é gravado
        self.assertEqual(documentos.listar(self.super["id"], self.pac), [])


class TestMigracao(unittest.TestCase):
    def test_banco_antigo_e_migrado_sem_perder_dados(self):
        with tempfile.TemporaryDirectory() as pasta:
            database.DB_PATH = Path(pasta) / "antigo.db"
            con = sqlite3.connect(database.DB_PATH)
            con.executescript("""
                CREATE TABLE especialidade (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE);
                CREATE TABLE paciente (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
                    cpf TEXT NOT NULL UNIQUE, data_nascimento TEXT NOT NULL, telefone TEXT, email TEXT);
                CREATE TABLE profissional (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
                    registro TEXT NOT NULL UNIQUE, especialidade_id INTEGER NOT NULL, telefone TEXT,
                    ativo INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE consulta (id INTEGER PRIMARY KEY AUTOINCREMENT, paciente_id INTEGER NOT NULL,
                    profissional_id INTEGER NOT NULL, data TEXT NOT NULL, hora_inicio TEXT NOT NULL,
                    hora_fim TEXT NOT NULL, situacao TEXT NOT NULL DEFAULT 'Agendada'
                    CHECK (situacao IN ('Agendada','Realizada','Cancelada')),
                    motivo_cancelamento TEXT, observacoes TEXT);
                INSERT INTO especialidade (nome) VALUES ('Pediatria');
                INSERT INTO paciente (nome, cpf, data_nascimento) VALUES ('Ana', '52998224725', '1990-01-01');
                INSERT INTO profissional (nome, registro, especialidade_id) VALUES ('Dr. X', 'CRM9', 1);
                INSERT INTO consulta (paciente_id, profissional_id, data, hora_inicio, hora_fim, situacao)
                    VALUES (1, 1, '2030-01-02', '09:00', '09:30', 'Realizada');
            """)
            con.commit()
            con.close()
            database.criar_tabelas()
            database.criar_tabelas()  # rodar duas vezes não pode quebrar
            c = consultas.listar()[0]
            self.assertEqual((c["situacao"], c["pagamento_status"], c["valor_centavos"]),
                             ("Realizada", "Aguardando pagamento", 0))
            self.assertEqual(pacientes.listar()[0]["ativo"], 1)
            self.assertEqual(especialidades.listar()[0]["valor_consulta"], 0)


if __name__ == "__main__":
    unittest.main()
