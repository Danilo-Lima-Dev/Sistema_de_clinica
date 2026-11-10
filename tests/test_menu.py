"""Testes do menu por papel (services/menu.py). Execute com:
    python -m unittest discover -s tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import acesso, menu  # noqa: E402
from services.autenticacao import PAPEIS, PAPEL_ADMIN, PAPEL_ATENDENTE, PAPEL_MEDICO  # noqa: E402


class TestMenuPorPapel(unittest.TestCase):
    def test_todo_papel_tem_menu_e_abre_em_consultas(self):
        for papel in PAPEIS:
            self.assertTrue(menu.telas_do_papel(papel), papel)
            self.assertEqual(menu.tela_inicial(papel), menu.CONSULTAS)

    def test_administrador(self):
        telas = menu.telas_do_papel(PAPEL_ADMIN)
        for tela in (menu.PROFISSIONAIS, menu.ESPECIALIDADES, menu.FINANCEIRO, menu.USUARIOS):
            self.assertIn(tela, telas)
        self.assertNotIn(menu.PRONTUARIO, telas)  # dado clínico não é do administrador

    def test_atendente(self):
        telas = menu.telas_do_papel(PAPEL_ATENDENTE)
        self.assertEqual(
            set(telas), {menu.CONSULTAS, menu.AGENDA, menu.PACIENTES, menu.DOCUMENTOS}
        )

    def test_medico(self):
        telas = menu.telas_do_papel(PAPEL_MEDICO)
        self.assertEqual(
            set(telas), {menu.CONSULTAS, menu.AGENDA, menu.PRONTUARIO, menu.HISTORICO}
        )
        for proibida in (menu.FINANCEIRO, menu.USUARIOS, menu.PROFISSIONAIS, menu.PACIENTES):
            self.assertNotIn(proibida, telas)

    def test_ninguem_repete_tela(self):
        for papel in PAPEIS:
            telas = menu.telas_do_papel(papel)
            self.assertEqual(len(telas), len(set(telas)))

    def test_papel_desconhecido_nao_ve_nada(self):
        for papel in (None, "", "Faxineiro"):
            self.assertEqual(menu.telas_do_papel(papel), ())
            self.assertIsNone(menu.tela_inicial(papel))


class TestBotoesPorPapel(unittest.TestCase):
    def test_quem_ve_cada_botao(self):
        casos = {
            menu.DESATIVAR_EXCLUIR_PACIENTE: {PAPEL_ADMIN},
            menu.GERIR_CONSULTAS: {PAPEL_ATENDENTE, PAPEL_ADMIN},
            menu.ATENDER: {PAPEL_MEDICO},
            menu.BLOQUEAR_AGENDA: {PAPEL_ADMIN, PAPEL_MEDICO},
        }
        for acao, permitidos in casos.items():
            for papel in PAPEIS:
                self.assertEqual(menu.pode(papel, acao), papel in permitidos, (acao, papel))

    def test_desconhecidos_nao_podem_nada(self):
        self.assertFalse(menu.pode(None, menu.GERIR_CONSULTAS))
        self.assertFalse(menu.pode("Faxineiro", menu.ATENDER))
        self.assertFalse(menu.pode(PAPEL_ADMIN, "acao_inexistente"))

    def test_botoes_acompanham_a_portaria_do_back_end(self):
        """Se alguém mudar a regra de um lado e esquecer do outro, este teste avisa."""
        self.assertEqual(set(menu.QUEM_PODE[menu.GERIR_CONSULTAS]), set(acesso.RECEPCAO_E_ADMIN))
        self.assertEqual(set(menu.QUEM_PODE[menu.DESATIVAR_EXCLUIR_PACIENTE]), set(acesso.SO_ADMIN))


if __name__ == "__main__":
    unittest.main()