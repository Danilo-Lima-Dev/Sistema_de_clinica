"""Testes dos papéis (Administrador, Atendente, Médico). Execute com:
    python -m unittest discover -s tests
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
from services import autenticacao, profissionais  # noqa: E402
from services.autenticacao import PAPEL_ADMIN, PAPEL_ATENDENTE, PAPEL_MEDICO  # noqa: E402
from services.validacoes import ErroValidacao  # noqa: E402


class TestPapeis(unittest.TestCase):
    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._pasta.name) / "t.db"
        database.criar_tabelas()
        autenticacao.criar_usuario_padrao()
        autenticacao.criar_superusuario_padrao()
        self.admin = autenticacao.autenticar("super", autenticacao.SUPER_SENHA)
        self.atendente = autenticacao.autenticar("admin", autenticacao.SENHA_PADRAO)
        self.id_prof = profissionais.cadastrar("Dra. Ana", "CRM 1", "Cardiologia")

    def tearDown(self):
        self._pasta.cleanup()

    def _cadastrar_medico(self, login="dra.ana", id_prof=None):
        autenticacao.cadastrar_usuario_por(
            self.admin["id"], "Dra. Ana", login, "senha123",
            papel=PAPEL_MEDICO, profissional_id=id_prof or self.id_prof,
        )
        return autenticacao.autenticar(login, "senha123")

    def test_usuarios_padrao_ganham_o_papel_certo(self):
        self.assertEqual(self.admin["papel"], PAPEL_ADMIN)
        self.assertTrue(self.admin["superusuario"])
        self.assertEqual(self.atendente["papel"], PAPEL_ATENDENTE)
        self.assertFalse(self.atendente["superusuario"])

    def test_medico_e_ligado_ao_profissional(self):
        medico = self._cadastrar_medico()
        self.assertEqual(medico["papel"], PAPEL_MEDICO)
        self.assertEqual(medico["profissional_id"], self.id_prof)
        self.assertFalse(medico["superusuario"])

    def test_medico_exige_profissional(self):
        with self.assertRaises(ErroValidacao):
            autenticacao.cadastrar_usuario_por(
                self.admin["id"], "Sem Vinculo", "semvinculo", "senha123", papel=PAPEL_MEDICO
            )

    def test_profissional_inexistente_ou_inativo_e_recusado(self):
        with self.assertRaises(ErroValidacao):
            self._cadastrar_medico("m1", id_prof=9999)
        profissionais.alternar_ativo(self.id_prof)  # desativa
        with self.assertRaises(ErroValidacao):
            self._cadastrar_medico("med2")

    def test_profissional_nao_pode_ter_dois_usuarios(self):
        self._cadastrar_medico("med1")
        with self.assertRaises(ErroValidacao):
            self._cadastrar_medico("med2")

    def test_so_medico_tem_profissional(self):
        with self.assertRaises(ErroValidacao):
            autenticacao.cadastrar_usuario_por(
                self.admin["id"], "Recepção", "recepcao", "senha123",
                papel=PAPEL_ATENDENTE, profissional_id=self.id_prof,
            )

    def test_papel_invalido_e_recusado(self):
        with self.assertRaises(ErroValidacao):
            autenticacao.cadastrar_usuario_por(
                self.admin["id"], "X", "xis", "senha123", papel="Faxineiro"
            )

    def test_so_administrador_cadastra_usuarios(self):
        medico = self._cadastrar_medico()
        for quem in (self.atendente, medico):
            with self.assertRaises(ErroValidacao):
                autenticacao.cadastrar_usuario_por(quem["id"], "Novo", "novo", "senha123")

    def test_exigir_papel_o_cadeado(self):
        medico = self._cadastrar_medico()
        # papel permitido: passa e devolve os dados
        dados = autenticacao.exigir_papel(medico["id"], PAPEL_MEDICO)
        self.assertEqual(dados["profissional_id"], self.id_prof)
        # papel não permitido: barrado
        with self.assertRaises(ErroValidacao):
            autenticacao.exigir_papel(self.atendente["id"], PAPEL_MEDICO)
        # vários papéis permitidos
        autenticacao.exigir_papel(self.atendente["id"], PAPEL_ATENDENTE, PAPEL_ADMIN)

    def test_usuario_desativado_perde_a_permissao(self):
        autenticacao.atualizar_usuario(
            self.admin["id"], self.atendente["id"], "Recepção", "admin", ativo=False,
            papel=PAPEL_ATENDENTE,
        )
        with self.assertRaises(ErroValidacao):
            autenticacao.exigir_papel(self.atendente["id"], PAPEL_ATENDENTE)

    def test_trocar_papel_mantem_a_coluna_antiga_alinhada(self):
        autenticacao.atualizar_usuario(
            self.admin["id"], self.atendente["id"], "Recepção", "admin", papel=PAPEL_ADMIN
        )
        self.assertTrue(autenticacao.autenticar("admin", autenticacao.SENHA_PADRAO)["superusuario"])
        # e o contrário: ao virar Atendente, deixa de ser super (há outro admin ativo)
        autenticacao.atualizar_usuario(
            self.admin["id"], self.atendente["id"], "Recepção", "admin", papel=PAPEL_ATENDENTE
        )
        self.assertFalse(autenticacao.autenticar("admin", autenticacao.SENHA_PADRAO)["superusuario"])

    def test_nao_deixa_o_sistema_sem_administrador(self):
        with self.assertRaises(ErroValidacao):
            autenticacao.atualizar_usuario(
                self.admin["id"], self.admin["id"], "Super", "super", papel=PAPEL_ATENDENTE
            )

    def test_trocar_de_medico_para_outro_papel_solta_o_vinculo(self):
        medico = self._cadastrar_medico()
        autenticacao.atualizar_usuario(
            self.admin["id"], medico["id"], "Dra. Ana", "dra.ana", papel=PAPEL_ATENDENTE
        )
        self.assertIsNone(autenticacao.autenticar("dra.ana", "senha123")["profissional_id"])
        # e o profissional fica livre para outro usuário
        self._cadastrar_medico("outro.login")


if __name__ == "__main__":
    unittest.main()