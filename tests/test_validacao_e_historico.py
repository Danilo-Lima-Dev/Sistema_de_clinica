"""Testes da validação na alteração de dados e do histórico clínico (só o médico).
Execute com:  python -m unittest discover -s tests
"""
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
from services import (  # noqa: E402
    acesso, autenticacao, consultas, especialidades, financeiro, historico_clinico, menu,
    pacientes, profissionais,
)
from services.autenticacao import PAPEL_ADMIN, PAPEL_ATENDENTE, PAPEL_MEDICO  # noqa: E402
from services.validacoes import ErroValidacao, validar_login, validar_nome, validar_registro  # noqa: E402

CPF = "52998224725"
CPF2 = "11144477735"


def dia_util(dias=1):
    dia = date.today() + timedelta(days=dias)
    while dia.weekday() >= 5:
        dia += timedelta(days=1)
    return dia.strftime("%d/%m/%Y")


class Base(unittest.TestCase):
    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._pasta.name) / "t.db"
        database.criar_tabelas()
        autenticacao.criar_usuario_padrao()
        autenticacao.criar_superusuario_padrao()
        self.admin = autenticacao.autenticar("super", autenticacao.SUPER_SENHA)
        self.atendente = autenticacao.autenticar("admin", autenticacao.SENHA_PADRAO)
        self.prof_a = profissionais.cadastrar("Dra. Ana", "CRM 1111", "Cardiologia")
        self.prof_b = profissionais.cadastrar("Dr. Bruno", "CRM 2222", "Pediatria")
        self.medico_a = self._medico("dra.ana", "Dra. Ana", self.prof_a)
        self.medico_b = self._medico("dr.bruno", "Dr. Bruno", self.prof_b)
        self.pac = pacientes.cadastrar("João Silva", CPF, "01/01/1990", "86982341234")

    def tearDown(self):
        self._pasta.cleanup()

    def _medico(self, login, nome, id_prof):
        autenticacao.cadastrar_usuario_por(
            self.admin["id"], nome, login, "senha123", papel=PAPEL_MEDICO, profissional_id=id_prof
        )
        return autenticacao.autenticar(login, "senha123")


class TestValidadores(unittest.TestCase):
    def test_nome(self):
        self.assertEqual(validar_nome("  Maria   da  Silva "), "Maria da Silva")
        self.assertEqual(validar_nome("Dra. Ana D'Ávila-Souza"), "Dra. Ana D'Ávila-Souza")
        for ruim in ("", "   ", "A", "João123", "Maria@", "x" * 101, "1234"):
            with self.assertRaises(ErroValidacao, msg=ruim):
                validar_nome(ruim)

    def test_mensagem_usa_o_rotulo(self):
        with self.assertRaises(ErroValidacao) as c:
            validar_nome("", "O nome do profissional")
        self.assertIn("profissional", str(c.exception))

    def test_registro(self):
        self.assertEqual(validar_registro("CRM 12345/SP"), "CRM 12345/SP")
        for ruim in ("", "CRM", "ABC", "CRM!!123", "1" * 31):
            with self.assertRaises(ErroValidacao, msg=ruim):
                validar_registro(ruim)

    def test_login(self):
        self.assertEqual(validar_login(" Dra.Ana "), "dra.ana")
        for ruim in ("", "ab", "com espaço", "a" * 31, "ação"):
            with self.assertRaises(ErroValidacao, msg=ruim):
                validar_login(ruim)


class TestAlteracaoDeDados(Base):
    def test_paciente_alteracao_invalida_e_recusada(self):
        for args in (("J", CPF, "01/01/1990"), ("João 9", CPF, "01/01/1990"),
                     ("João Silva", "123", "01/01/1990"), ("João Silva", CPF, "01/01/2999")):
            with self.assertRaises(ErroValidacao):
                acesso.atualizar_paciente(self.atendente["id"], self.pac, *args)
        self.assertEqual(pacientes.obter(self.pac)["nome"], "João Silva")  # nada mudou

    def test_paciente_houve_mudanca(self):
        igual = ("João Silva", CPF, "01/01/1990", "86982341234", "")
        self.assertFalse(pacientes.houve_mudanca(self.pac, *igual))
        self.assertTrue(pacientes.houve_mudanca(self.pac, "João Souza", *igual[1:]))
        self.assertTrue(pacientes.houve_mudanca(self.pac, *igual[:3], "86982341235", ""))
        with self.assertRaises(ErroValidacao):
            pacientes.houve_mudanca(self.pac, "J", *igual[1:])
        with self.assertRaises(ErroValidacao):
            pacientes.houve_mudanca(9999, *igual)

    def test_cpf_repetido_na_alteracao(self):
        outro = pacientes.cadastrar("Maria Souza", CPF2, "02/02/1992")
        with self.assertRaises(ErroValidacao):
            acesso.atualizar_paciente(self.atendente["id"], outro, "Maria Souza", CPF, "02/02/1992")

    def test_profissional_validacao_e_mudanca(self):
        with self.assertRaises(ErroValidacao):
            acesso.atualizar_profissional(self.admin["id"], self.prof_a, "Dra. Ana", "CRM", "Cardiologia")
        with self.assertRaises(ErroValidacao):
            acesso.atualizar_profissional(self.admin["id"], self.prof_a, "A", "CRM 1111", "Cardiologia")
        self.assertFalse(profissionais.houve_mudanca(self.prof_a, "Dra. Ana", "CRM 1111", "Cardiologia"))
        self.assertTrue(profissionais.houve_mudanca(self.prof_a, "Dra. Ana", "CRM 1112", "Cardiologia"))
        antes = len(profissionais.listar_especialidades())
        self.assertTrue(profissionais.houve_mudanca(self.prof_a, "Dra. Ana", "CRM 1111", "Especialidade Nova"))
        self.assertEqual(len(profissionais.listar_especialidades()), antes)  # não criou nada

    def test_especialidade(self):
        esp = especialidades.listar()[0]
        with self.assertRaises(ErroValidacao):
            acesso.atualizar_especialidade(self.admin["id"], esp["id"], "X")
        self.assertFalse(especialidades.houve_mudanca(esp["id"], esp["nome"]))
        self.assertTrue(especialidades.houve_mudanca(esp["id"], esp["nome"] + " Geral"))

    def test_tela_especialidade_salva_com_valor(self):
        """Era um erro (executor_id duplicado) na chamada que a tela faz ao salvar."""
        eu = self.admin["id"]
        nova = acesso.cadastrar_especialidade(eu, "Neurologia", 15000)
        self.assertEqual(especialidades.obter(nova)["valor_consulta"], 15000)
        acesso.atualizar_especialidade(eu, nova, "Neurologia Clínica", 18000)
        self.assertEqual(especialidades.obter(nova)["valor_consulta"], 18000)

    def test_usuario(self):
        uid = self.atendente["id"]
        eu = self.admin["id"]
        for args in (("Ad", "ab"), ("Admin 1", "admin"), ("Admin", "com espaço")):
            with self.assertRaises(ErroValidacao):
                autenticacao.atualizar_usuario(eu, uid, *args)
        with self.assertRaises(ErroValidacao):  # senha igual ao login
            autenticacao.atualizar_usuario(eu, uid, "Admin", "admin", "admin")
        with self.assertRaises(ErroValidacao):  # senha com espaço nas pontas
            autenticacao.atualizar_usuario(eu, uid, "Admin", "admin", " senha123 ")
        self.assertFalse(autenticacao.houve_mudanca_usuario(
            eu, uid, "Administrador", "admin", "", True, PAPEL_ATENDENTE))
        self.assertTrue(autenticacao.houve_mudanca_usuario(
            eu, uid, "Administrador", "admin", "novasenha", True, PAPEL_ATENDENTE))
        with self.assertRaises(ErroValidacao):  # só o administrador
            autenticacao.houve_mudanca_usuario(self.atendente["id"], uid, "A B", "abc")

    def test_consulta_paga_nao_troca_paciente_nem_medico(self):
        outro = pacientes.cadastrar("Maria Souza", CPF2, "02/02/1992")
        dia = dia_util()
        cid = consultas.agendar(self.pac, self.prof_a, dia, "09:00")
        financeiro.registrar_pagamento(self.atendente["id"], cid)
        with self.assertRaises(ErroValidacao):
            acesso.alterar_consulta(self.atendente["id"], cid, outro, self.prof_a, dia, "09:00")
        with self.assertRaises(ErroValidacao):
            acesso.alterar_consulta(self.atendente["id"], cid, self.pac, self.prof_b, dia, "09:00")
        # remarcar o horário continua permitido
        acesso.alterar_consulta(self.atendente["id"], cid, self.pac, self.prof_a, dia, "10:00")
        self.assertEqual(consultas.obter(cid)["hora_inicio"], "10:00")

    def test_observacoes_muito_longas(self):
        with self.assertRaises(ErroValidacao):
            consultas.agendar(self.pac, self.prof_a, dia_util(), "09:00", "x" * 501)
        consultas.agendar(self.pac, self.prof_a, dia_util(), "09:00", "x" * 500)


class TestHistoricoClinico(Base):
    def test_so_medico_acessa(self):
        for quem in (self.admin, self.atendente):
            with self.assertRaises(ErroValidacao):
                historico_clinico.listar(quem["id"], self.pac)
            with self.assertRaises(ErroValidacao):
                historico_clinico.adicionar(quem["id"], self.pac, "Paciente com dor de cabeça")
            with self.assertRaises(ErroValidacao):
                historico_clinico.revisoes(quem["id"], 1)
        with self.assertRaises(ErroValidacao):
            historico_clinico.listar(None, self.pac)
        with self.assertRaises(ErroValidacao):
            historico_clinico.listar(9999, self.pac)

    def test_medico_inativo_perde_o_acesso(self):
        autenticacao.atualizar_usuario(
            self.admin["id"], self.medico_a["id"], "Dra. Ana", "dra.ana", ativo=False,
            papel=PAPEL_MEDICO, profissional_id=self.prof_a,
        )
        with self.assertRaises(ErroValidacao):
            historico_clinico.listar(self.medico_a["id"], self.pac)

    def test_adicionar_e_listar(self):
        cid = consultas.agendar(self.pac, self.prof_a, dia_util(), "09:00")
        historico_clinico.adicionar(self.medico_a["id"], self.pac, "Queixa de cefaleia há 3 dias.", cid)
        historico_clinico.adicionar(self.medico_b["id"], self.pac, "Retorno em 15 dias.")
        lista = historico_clinico.listar(self.medico_a["id"], self.pac)
        self.assertEqual(len(lista), 2)
        self.assertEqual({a["autor_nome"] for a in lista}, {"Dra. Ana", "Dr. Bruno"})  # médicos leem os dos outros
        self.assertEqual(len(historico_clinico.consultas_do_paciente(self.medico_a["id"], self.pac)), 1)

    def test_texto_invalido(self):
        for ruim in ("", "   ", "ab", "x" * 5001):
            with self.assertRaises(ErroValidacao, msg=ruim[:10]):
                historico_clinico.adicionar(self.medico_a["id"], self.pac, ruim)

    def test_consulta_de_outro_paciente_ou_cancelada(self):
        outro = pacientes.cadastrar("Maria Souza", CPF2, "02/02/1992")
        c_outro = consultas.agendar(outro, self.prof_a, dia_util(), "09:00")
        with self.assertRaises(ErroValidacao):
            historico_clinico.adicionar(self.medico_a["id"], self.pac, "Anotação válida", c_outro)
        acesso.cancelar_consulta(self.atendente["id"], c_outro, "teste")
        with self.assertRaises(ErroValidacao):
            historico_clinico.adicionar(self.medico_a["id"], outro, "Anotação válida", c_outro)
        with self.assertRaises(ErroValidacao):
            historico_clinico.adicionar(self.medico_a["id"], 9999, "Anotação válida")

    def test_so_o_autor_altera_e_a_versao_anterior_fica(self):
        id_a = historico_clinico.adicionar(self.medico_a["id"], self.pac, "Texto original")
        with self.assertRaises(ErroValidacao):  # outro médico
            historico_clinico.alterar(self.medico_b["id"], id_a, "Texto trocado")
        for quem in (self.admin, self.atendente):
            with self.assertRaises(ErroValidacao):
                historico_clinico.alterar(quem["id"], id_a, "Texto trocado")
        self.assertFalse(historico_clinico.alterar(self.medico_a["id"], id_a, "Texto original"))
        self.assertEqual(historico_clinico.revisoes(self.medico_a["id"], id_a), [])
        self.assertTrue(historico_clinico.alterar(self.medico_a["id"], id_a, "Texto corrigido"))
        a = historico_clinico.listar(self.medico_a["id"], self.pac)[0]
        self.assertEqual(a["texto"], "Texto corrigido")
        self.assertEqual(a["atualizado_por"], "Dra. Ana")
        revs = historico_clinico.revisoes(self.medico_b["id"], id_a)
        self.assertEqual([r["texto_anterior"] for r in revs], ["Texto original"])
        with self.assertRaises(ErroValidacao):
            historico_clinico.alterar(self.medico_a["id"], 9999, "Texto qualquer")

    def test_paciente_com_historico_nao_e_excluido(self):
        historico_clinico.adicionar(self.medico_a["id"], self.pac, "Primeira anotação")
        with self.assertRaises(ErroValidacao):
            acesso.excluir_paciente(self.admin["id"], self.pac)
        self.assertIsNotNone(pacientes.obter(self.pac))

    def test_profissional_ligado_a_usuario_nao_e_excluido(self):
        with self.assertRaises(ErroValidacao):
            acesso.excluir_profissional(self.admin["id"], self.prof_a)

    def test_menu_so_do_medico(self):
        self.assertIn(menu.HISTORICO, menu.telas_do_papel(PAPEL_MEDICO))
        self.assertNotIn(menu.HISTORICO, menu.telas_do_papel(PAPEL_ADMIN))
        self.assertNotIn(menu.HISTORICO, menu.telas_do_papel(PAPEL_ATENDENTE))


if __name__ == "__main__":
    unittest.main()
