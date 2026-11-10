"""Testes do histórico clínico por paciente (services/historico.py).
Execute com:  python -m unittest discover -s tests
"""
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
from services import autenticacao, consultas, historico, menu, pacientes, profissionais  # noqa: E402
from services.autenticacao import PAPEL_MEDICO  # noqa: E402
from services.validacoes import ErroValidacao  # noqa: E402

CPF = "52998224725"


def dia_util(passo):
    """Dia útil mais próximo andando `passo` dias (-1 = passado, +1 = futuro)."""
    dia = date.today() + timedelta(days=passo)
    while dia.weekday() >= 5:
        dia += timedelta(days=passo)
    return dia.strftime("%d/%m/%Y")


class TestHistoricoClinico(unittest.TestCase):
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

        self.pac = pacientes.cadastrar("João Silva", CPF, "01/01/1990")
        ontem = dia_util(-1)
        self.consulta_a = consultas.agendar(self.pac, self.prof_a, ontem, "09:00", validar_futuro=False)
        self.consulta_b = consultas.agendar(self.pac, self.prof_b, ontem, "10:00", validar_futuro=False)
        self.consulta_futura = consultas.agendar(self.pac, self.prof_a, dia_util(1), "11:00")

    def tearDown(self):
        self._pasta.cleanup()

    def _novo_medico(self, login, nome, id_prof):
        autenticacao.cadastrar_usuario_por(
            self.admin["id"], nome, login, "senha123", papel=PAPEL_MEDICO, profissional_id=id_prof
        )
        return autenticacao.autenticar(login, "senha123")

    def _registrar_a(self):
        return historico.registrar(
            self.medico_a["id"], self.consulta_a, "Dor no peito", "I20", "ECG e retorno em 15 dias"
        )

    # ------------------------------------------------------------ acesso
    def test_so_medico_acessa(self):
        id_h = self._registrar_a()
        for quem in (self.admin, self.atendente):
            with self.assertRaises(ErroValidacao):
                historico.listar(quem["id"], self.pac)
            with self.assertRaises(ErroValidacao):
                historico.obter(quem["id"], id_h)
            with self.assertRaises(ErroValidacao):
                historico.registrar(quem["id"], self.consulta_a, "x")
            with self.assertRaises(ErroValidacao):
                historico.alterar(quem["id"], id_h, "y")
        with self.assertRaises(ErroValidacao):
            historico.listar(None, self.pac)

    def test_medico_ve_todo_o_historico_do_paciente(self):
        self._registrar_a()
        historico.registrar(self.medico_b["id"], self.consulta_b, "Febre", "", "Antitérmico")
        lista = historico.listar(self.medico_a["id"], self.pac)
        self.assertEqual(len(lista), 2)
        proprio = {h["consulta_id"]: h["pode_alterar"] for h in lista}
        self.assertTrue(proprio[self.consulta_a])
        self.assertFalse(proprio[self.consulta_b])  # vê, mas não altera o do colega

    def test_menu_so_do_medico(self):
        self.assertIn(menu.HISTORICO, menu.telas_do_papel(PAPEL_MEDICO))
        for papel in (autenticacao.PAPEL_ADMIN, autenticacao.PAPEL_ATENDENTE):
            self.assertNotIn(menu.HISTORICO, menu.telas_do_papel(papel))

    # ------------------------------------------------------------ registrar
    def test_registrar_e_ler(self):
        id_h = self._registrar_a()
        h = historico.obter(self.medico_a["id"], id_h)
        self.assertEqual(h["diagnostico"], "I20")
        self.assertEqual(h["medico_nome"], "Dra. Ana")
        self.assertEqual(historico.consultas_para_registrar(self.medico_a["id"], self.pac), [])

    def test_nao_registra_consulta_de_outro_medico(self):
        with self.assertRaises(ErroValidacao):
            historico.registrar(self.medico_a["id"], self.consulta_b, "x")

    def test_nao_registra_consulta_futura_cancelada_ou_repetida(self):
        with self.assertRaises(ErroValidacao):
            historico.registrar(self.medico_a["id"], self.consulta_futura, "x")
        self._registrar_a()
        with self.assertRaises(ErroValidacao):
            historico.registrar(self.medico_a["id"], self.consulta_a, "de novo")
        consultas.cancelar(self.consulta_b)
        with self.assertRaises(ErroValidacao):
            historico.registrar(self.medico_b["id"], self.consulta_b, "x")

    def test_registro_vazio_ou_longo_demais(self):
        with self.assertRaises(ErroValidacao):
            historico.registrar(self.medico_a["id"], self.consulta_a, "  ", "", "")
        with self.assertRaises(ErroValidacao):
            historico.registrar(self.medico_a["id"], self.consulta_a, "x" * 5000)

    def test_consultas_para_registrar(self):
        lista = historico.consultas_para_registrar(self.medico_a["id"], self.pac)
        self.assertEqual([c["id"] for c in lista], [self.consulta_a])  # nem futura nem do colega

    # ------------------------------------------------------------ alterar
    def test_so_o_autor_altera_e_a_versao_anterior_fica_guardada(self):
        id_h = self._registrar_a()
        with self.assertRaises(ErroValidacao):
            historico.alterar(self.medico_b["id"], id_h, "Outra coisa")
        historico.alterar(self.medico_a["id"], id_h, "Dor no peito ao esforço", "I20.9", "ECG")
        h = historico.obter(self.medico_a["id"], id_h)
        self.assertEqual(h["diagnostico"], "I20.9")
        self.assertIsNotNone(h["alterado_em"])
        versoes = historico.listar_versoes(self.medico_a["id"], id_h)
        self.assertEqual(len(versoes), 1)
        self.assertEqual(versoes[0]["diagnostico"], "I20")

    def test_alterar_sem_mudar_nada_avisa(self):
        id_h = self._registrar_a()
        with self.assertRaises(ErroValidacao):
            historico.alterar(
                self.medico_a["id"], id_h, "Dor no peito", "I20", "ECG e retorno em 15 dias"
            )
        self.assertEqual(historico.listar_versoes(self.medico_a["id"], id_h), [])


class TestValidacaoNaAlteracao(unittest.TestCase):
    """Validação na alteração dos dados de pacientes, profissionais e usuários."""

    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._pasta.name) / "t.db"
        database.criar_tabelas()
        autenticacao.criar_superusuario_padrao()
        self.admin = autenticacao.autenticar("super", autenticacao.SUPER_SENHA)
        self.pac = pacientes.cadastrar("Ana Souza", CPF, "25/03/1990", "86982341234", "a@x.com")
        self.prof = profissionais.cadastrar("Dr. Carlos", "CRM 333", "Ortopedia")

    def tearDown(self):
        self._pasta.cleanup()

    def test_paciente_sem_alteracao_avisa(self):
        with self.assertRaises(ErroValidacao):
            pacientes.atualizar(self.pac, "Ana Souza", CPF, "25/03/1990", "86982341234", "a@x.com")

    def test_paciente_dados_invalidos_na_alteracao(self):
        for nome, nasc in (("Ana 2", "25/03/1990"), ("A", "25/03/1990"),
                           ("Ana Souza", "01/01/1800"), ("Ana Souza", "31/02/2000")):
            with self.assertRaises(ErroValidacao):
                pacientes.atualizar(self.pac, nome, CPF, nasc)
        self.assertEqual(pacientes.obter(self.pac)["nome"], "Ana Souza")  # nada mudou

    def test_paciente_inexistente(self):
        with self.assertRaises(ErroValidacao):
            pacientes.atualizar(999, "Beto", CPF, "01/01/1990")

    def test_profissional_validacoes(self):
        with self.assertRaises(ErroValidacao):  # sem alteração
            profissionais.atualizar(self.prof, "Dr. Carlos", "CRM 333", "Ortopedia")
        with self.assertRaises(ErroValidacao):  # registro sem número
            profissionais.atualizar(self.prof, "Dr. Carlos", "CRM", "Ortopedia")
        with self.assertRaises(ErroValidacao):  # nome com número
            profissionais.atualizar(self.prof, "Dr. Carlos 2", "CRM 333", "Ortopedia")
        profissionais.atualizar(self.prof, "Dr. Carlos", "crm-pi 333", "Ortopedia")
        self.assertEqual(profissionais.obter(self.prof)["registro"], "CRM-PI 333")

    def test_usuario_login_e_nome(self):
        for nome, login in (("Ana", "a b"), ("Ana", "ab"), ("Ana1", "ana"), ("Ana", "ána")):
            with self.assertRaises(ErroValidacao):
                autenticacao.cadastrar_usuario_por(self.admin["id"], nome, login, "senha123")


if __name__ == "__main__":
    unittest.main()
