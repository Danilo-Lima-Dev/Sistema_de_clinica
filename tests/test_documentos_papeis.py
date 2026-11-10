"""Testes de quem pode o quê com atestados, receituários e a 2ª via (papéis).
Execute com:  python -m unittest discover -s tests
"""
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
from services import (  # noqa: E402
    atestado, autenticacao, consultas, documentos, pacientes, profissionais, receituario,
)
from services.autenticacao import PAPEL_MEDICO  # noqa: E402
from services.validacoes import ErroValidacao  # noqa: E402

CPF = "52998224725"


def proximo_dia_util():
    dia = date.today() + timedelta(days=1)
    while dia.weekday() >= 5:  # pula sábado e domingo
        dia += timedelta(days=1)
    return dia.strftime("%d/%m/%Y")


class TestDocumentosPorPapel(unittest.TestCase):
    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._pasta.name) / "t.db"
        database.criar_tabelas()
        autenticacao.criar_usuario_padrao()
        autenticacao.criar_superusuario_padrao()
        self.admin = autenticacao.autenticar("super", autenticacao.SUPER_SENHA)
        self.atendente = autenticacao.autenticar("admin", autenticacao.SENHA_PADRAO)

        self.prof_a = profissionais.cadastrar("Dra. Ana", "CRM 1", "Cardiologia")
        self.prof_b = profissionais.cadastrar("Dr. Bruno", "CRM 2", "Pediatria")
        self.medico_a = self._novo_medico("dra.ana", "Dra. Ana", self.prof_a)
        self.medico_b = self._novo_medico("dr.bruno", "Dr. Bruno", self.prof_b)

        self.pac = pacientes.cadastrar("João Silva", CPF, "01/01/1990", "86982341234", "j@x.com")
        dia = proximo_dia_util()
        self.consulta_a = consultas.agendar(self.pac, self.prof_a, dia, "09:00")
        self.consulta_b = consultas.agendar(self.pac, self.prof_b, dia, "10:00")

        # a Dra. Ana emite um atestado de uma consulta dela
        with mock.patch("webbrowser.open", return_value=True):
            atestado.imprimir(self.consulta_a, "2", "J11", "Teresina - PI", usuario=self.medico_a)
        self.id_doc = documentos.listar(self.medico_a["id"], self.pac)[0]["id"]

    def tearDown(self):
        self._pasta.cleanup()

    def _novo_medico(self, login, nome, id_prof):
        autenticacao.cadastrar_usuario_por(
            self.admin["id"], nome, login, "senha123", papel=PAPEL_MEDICO, profissional_id=id_prof
        )
        return autenticacao.autenticar(login, "senha123")

    # ------------------------------------------------------------ emitir
    def test_so_medico_emite_atestado(self):
        for quem in (self.atendente, self.admin):
            with mock.patch("webbrowser.open", return_value=True) as navegador:
                with self.assertRaises(ErroValidacao):
                    atestado.imprimir(self.consulta_a, "1", usuario=quem)
                navegador.assert_not_called()  # nem abriu o documento
        self.assertEqual(len(documentos.listar(self.medico_a["id"], self.pac)), 1)  # nada novo

    def test_so_medico_emite_receituario(self):
        with mock.patch("webbrowser.open", return_value=True):
            for quem in (self.atendente, self.admin):
                with self.assertRaises(ErroValidacao):
                    receituario.imprimir(self.consulta_a, "Dipirona 500 mg", usuario=quem)
            receituario.imprimir(self.consulta_a, "Dipirona 500 mg", usuario=self.medico_a)
        self.assertEqual(len(documentos.listar(self.medico_a["id"], self.pac)), 2)

    def test_medico_nao_emite_de_consulta_de_outro(self):
        with mock.patch("webbrowser.open", return_value=True):
            with self.assertRaises(ErroValidacao):
                atestado.imprimir(self.consulta_b, "1", usuario=self.medico_a)

    def test_sem_usuario_nao_emite(self):
        with self.assertRaises(ErroValidacao):
            atestado.imprimir(self.consulta_a, "1")

    # ------------------------------------------------------------ ver
    def test_listar_todos_os_papeis_sem_conteudo(self):
        for quem in (self.admin, self.atendente, self.medico_a):
            lista = documentos.listar(quem["id"], self.pac)
            self.assertEqual(len(lista), 1)
            self.assertNotIn("texto", lista[0])  # a lista nunca traz o conteúdo clínico
            self.assertNotIn("html", lista[0])

    def test_ver_conteudo_atendente_e_medico_sim_administrador_nao(self):
        for quem in (self.atendente, self.medico_a):
            self.assertIn("João Silva", documentos.obter(quem["id"], self.id_doc)["texto"])
        with self.assertRaises(ErroValidacao):
            documentos.obter(self.admin["id"], self.id_doc)

    def test_medico_so_ve_os_documentos_das_suas_consultas(self):
        self.assertEqual(documentos.listar(self.medico_b["id"], self.pac), [])
        with self.assertRaises(ErroValidacao):
            documentos.obter(self.medico_b["id"], self.id_doc)

    def test_sem_login_nao_ve_nada(self):
        with self.assertRaises(ErroValidacao):
            documentos.listar(None, self.pac)
        with self.assertRaises(ErroValidacao):
            documentos.obter(None, self.id_doc)

    def test_usuario_desativado_perde_o_acesso(self):
        autenticacao.atualizar_usuario(
            self.admin["id"], self.atendente["id"], "Recepção", "admin", ativo=False
        )
        with self.assertRaises(ErroValidacao):
            documentos.obter(self.atendente["id"], self.id_doc)

    # ------------------------------------------------------------ reimprimir (médico)
    def test_so_o_medico_dono_reimprime_direto(self):
        with mock.patch("webbrowser.open", return_value=True):
            self.assertTrue(documentos.reimprimir(self.medico_a["id"], self.id_doc).exists())
            for quem in (self.atendente, self.admin, self.medico_b):
                with self.assertRaises(ErroValidacao):
                    documentos.reimprimir(quem["id"], self.id_doc)

    # ------------------------------------------------------------ 2ª via pela recepção
    def _entregar(self, quem=None, **mudancas):
        dados = dict(forma="Impressão", destinatario_nome="Maria Silva",
                     vinculo="Responsável legal", destinatario_documento="12345678900")
        dados.update(mudancas)
        quem = quem or self.atendente
        with mock.patch("webbrowser.open", return_value=True):
            return documentos.entregar_segunda_via(
                quem["id"], self.id_doc, dados["forma"], dados["destinatario_nome"],
                dados["vinculo"], dados["destinatario_documento"],
            )

    def test_atendente_entrega_e_a_entrega_fica_registrada(self):
        self.assertTrue(self._entregar().exists())
        entregas = documentos.listar_entregas(self.admin["id"])
        self.assertEqual(len(entregas), 1)
        e = entregas[0]
        self.assertEqual(e["destinatario_nome"], "Maria Silva")
        self.assertEqual(e["destinatario_vinculo"], "Responsável legal")
        self.assertEqual(e["paciente_nome"], "João Silva")
        self.assertEqual(e["usuario_nome"], self.atendente["nome"])
        self.assertNotIn("texto", e)  # a auditoria não mostra o conteúdo clínico

    def test_entrega_exige_identificacao_de_quem_recebe(self):
        for erro in (
            dict(destinatario_nome="  "),
            dict(destinatario_documento=""),
            dict(vinculo="Vizinho"),
            dict(forma="WhatsApp"),
        ):
            with self.assertRaises(ErroValidacao):
                self._entregar(**erro)
        self.assertEqual(documentos.listar_entregas(self.admin["id"]), [])  # nada foi registrado

    def test_entrega_em_pdf_tambem_e_registrada(self):
        self._entregar(forma="PDF", vinculo="Próprio paciente")
        self.assertEqual(documentos.listar_entregas(self.admin["id"])[0]["forma"], "PDF")

    def test_so_o_atendente_entrega_a_segunda_via(self):
        for quem in (self.admin, self.medico_a):
            with self.assertRaises(ErroValidacao):
                self._entregar(quem)
        self.assertEqual(documentos.listar_entregas(self.admin["id"]), [])

    def test_so_o_administrador_ve_o_registro_de_entregas(self):
        self._entregar()
        for quem in (self.atendente, self.medico_a):
            with self.assertRaises(ErroValidacao):
                documentos.listar_entregas(quem["id"])


if __name__ == "__main__":
    unittest.main()