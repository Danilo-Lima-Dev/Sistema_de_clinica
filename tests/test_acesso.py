"""Testes da "portaria" (services/acesso.py): quem pode cadastrar, agendar e bloquear agenda.
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
    acesso, agenda, autenticacao, consultas, especialidades, pacientes, profissionais,
)
from services.autenticacao import PAPEL_MEDICO  # noqa: E402
from services.validacoes import ErroValidacao  # noqa: E402

CPF = "52998224725"
CPF_2 = "11144477735"


def proximo_dia_util():
    dia = date.today() + timedelta(days=1)
    while dia.weekday() >= 5:  # pula sábado e domingo
        dia += timedelta(days=1)
    return dia


class Base(unittest.TestCase):
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
        self.dia = proximo_dia_util()

    def tearDown(self):
        self._pasta.cleanup()

    def _novo_medico(self, login, nome, id_prof):
        autenticacao.cadastrar_usuario_por(
            self.admin["id"], nome, login, "senha123", papel=PAPEL_MEDICO, profissional_id=id_prof
        )
        return autenticacao.autenticar(login, "senha123")

    def negado(self, funcao, *args, **kwargs):
        with self.assertRaises(ErroValidacao):
            funcao(*args, **kwargs)


class TestPortariaPacientes(Base):
    def test_recepcao_e_admin_cadastram_e_alteram(self):
        novo = acesso.cadastrar_paciente(self.atendente["id"], "Maria Souza", CPF_2, "02/02/1985")
        acesso.atualizar_paciente(
            self.admin["id"], novo, "Maria S. Souza", CPF_2, "02/02/1985", "86981112222", ""
        )
        self.assertEqual(pacientes.obter(novo)["nome"], "Maria S. Souza")

    def test_medico_e_desconhecidos_nao_cadastram_nem_alteram(self):
        antes = len(pacientes.listar())
        for quem in (self.medico_a["id"], None, 9999):
            self.negado(acesso.cadastrar_paciente, quem, "Maria Souza", CPF_2, "02/02/1985")
            self.negado(acesso.atualizar_paciente, quem, self.pac, "Outro Nome", CPF, "01/01/1990")
        self.assertEqual(len(pacientes.listar()), antes)
        self.assertEqual(pacientes.obter(self.pac)["nome"], "João Silva")

    def test_desativar_e_excluir_so_administrador(self):
        for quem in (self.atendente, self.medico_a):
            self.negado(acesso.alternar_ativo_paciente, quem["id"], self.pac)
            self.negado(acesso.excluir_paciente, quem["id"], self.pac)
        self.assertTrue(pacientes.obter(self.pac)["ativo"])
        acesso.alternar_ativo_paciente(self.admin["id"], self.pac)
        self.assertFalse(pacientes.obter(self.pac)["ativo"])
        acesso.excluir_paciente(self.admin["id"], self.pac)
        self.assertIsNone(pacientes.obter(self.pac))

    def test_a_portaria_nao_esconde_os_erros_de_validacao(self):
        with self.assertRaises(ErroValidacao) as erro:  # CPF repetido (regra do serviço)
            acesso.cadastrar_paciente(self.atendente["id"], "Clone", CPF, "01/01/1990")
        self.assertNotIn("Somente", str(erro.exception))


class TestPortariaProfissionaisEEspecialidades(Base):
    def test_so_administrador_gerencia_profissionais(self):
        for quem in (self.atendente, self.medico_a):
            self.negado(acesso.cadastrar_profissional, quem["id"], "Dr. X", "CRM 9", "Cardiologia")
            self.negado(acesso.atualizar_profissional, quem["id"], self.prof_a, "Dra. Ana", "CRM 1", "Cardiologia")
            self.negado(acesso.alternar_ativo_profissional, quem["id"], self.prof_a)
            self.negado(acesso.excluir_profissional, quem["id"], self.prof_b)
        novo = acesso.cadastrar_profissional(self.admin["id"], "Dr. X", "CRM 9", "Cardiologia")
        acesso.atualizar_profissional(self.admin["id"], novo, "Dr. X Y", "CRM 9", "Cardiologia")
        acesso.alternar_ativo_profissional(self.admin["id"], novo)
        self.assertFalse(profissionais.obter(novo)["ativo"])
        acesso.excluir_profissional(self.admin["id"], novo)

    def test_so_administrador_gerencia_especialidades(self):
        for quem in (self.atendente, self.medico_a):
            self.negado(acesso.cadastrar_especialidade, quem["id"], "Neurologia")
        nova = acesso.cadastrar_especialidade(self.admin["id"], "Neurologia")
        for quem in (self.atendente, self.medico_a):
            self.negado(acesso.atualizar_especialidade, quem["id"], nova, "Neuro")
            self.negado(acesso.excluir_especialidade, quem["id"], nova)
        acesso.atualizar_especialidade(self.admin["id"], nova, "Neurologia Clínica")
        acesso.excluir_especialidade(self.admin["id"], nova)
        self.assertEqual(especialidades.listar("neuro"), [])


class TestPortariaConsultas(Base):
    def agendar_como(self, quem, hora="09:00"):
        return acesso.agendar_consulta(
            quem["id"], self.pac, self.prof_a, self.dia.strftime("%d/%m/%Y"), hora
        )

    def test_recepcao_e_admin_agendam_remarcam_e_cancelam(self):
        id_c = self.agendar_como(self.atendente)
        acesso.alterar_consulta(
            self.admin["id"], id_c, self.pac, self.prof_a, self.dia.strftime("%d/%m/%Y"), "10:00"
        )
        self.assertEqual(consultas.obter(id_c)["hora_inicio"], "10:00")
        acesso.cancelar_consulta(self.atendente["id"], id_c, "Imprevisto")
        self.assertEqual(consultas.obter(id_c)["situacao"], "Cancelada")

    def test_medico_nao_agenda_remarca_nem_cancela(self):
        id_c = self.agendar_como(self.atendente)
        self.negado(self.agendar_como, self.medico_a, "11:00")
        self.negado(acesso.alterar_consulta, self.medico_a["id"], id_c, self.pac, self.prof_a,
                    self.dia.strftime("%d/%m/%Y"), "10:00")
        self.negado(acesso.cancelar_consulta, self.medico_a["id"], id_c, "x")
        self.assertEqual(consultas.obter(id_c)["situacao"], "Agendada")
        self.assertEqual(len(consultas.listar()), 1)

    def test_conflito_de_horario_continua_valendo_pela_portaria(self):
        self.agendar_como(self.atendente, "09:00")
        self.negado(self.agendar_como, self.atendente, "09:15")


class TestPortariaAgenda(Base):
    def test_medico_bloqueia_e_libera_a_propria_agenda(self):
        acesso.bloquear_horario(self.medico_a["id"], self.prof_a, self.dia, "10:00", "Reunião")
        estados = {h["hora_inicio"]: h["estado"] for h in agenda.horarios_do_dia(self.prof_a, self.dia)}
        self.assertEqual(estados["10:00"], "indisponivel")
        acesso.liberar_horario(self.medico_a["id"], self.prof_a, self.dia, "10:00")
        acesso.bloquear_dia(self.medico_a["id"], self.prof_a, self.dia, "Congresso")
        acesso.liberar_dia(self.medico_a["id"], self.prof_a, self.dia)

    def test_medico_nao_mexe_na_agenda_de_outro(self):
        self.negado(acesso.bloquear_horario, self.medico_a["id"], self.prof_b, self.dia, "10:00")
        self.negado(acesso.bloquear_dia, self.medico_a["id"], self.prof_b, self.dia)
        estados = {h["hora_inicio"]: h["estado"] for h in agenda.horarios_do_dia(self.prof_b, self.dia)}
        self.assertEqual(estados["10:00"], "disponivel")

    def test_administrador_mexe_em_qualquer_agenda(self):
        acesso.bloquear_horario(self.admin["id"], self.prof_b, self.dia, "10:00")
        acesso.liberar_horario(self.admin["id"], self.prof_b, self.dia, "10:00")

    def test_atendente_nao_bloqueia_agenda(self):
        self.negado(acesso.bloquear_horario, self.atendente["id"], self.prof_a, self.dia, "10:00")
        self.negado(acesso.liberar_dia, self.atendente["id"], self.prof_a, self.dia)


if __name__ == "__main__":
    unittest.main()