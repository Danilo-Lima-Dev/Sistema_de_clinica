"""Testes de quem pode o quê com pagamento, confirmação e consulta realizada (papéis).
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
    autenticacao, consultas, especialidades, financeiro, pacientes, profissionais,
)
from services.autenticacao import PAPEL_MEDICO  # noqa: E402
from services.validacoes import ErroValidacao  # noqa: E402

CPF = "52998224725"


def proximo_dia_util():
    dia = date.today() + timedelta(days=1)
    while dia.weekday() >= 5:  # pula sábado e domingo
        dia += timedelta(days=1)
    return dia.strftime("%d/%m/%Y")


class TestPagamentoEConsultaPorPapel(unittest.TestCase):
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
        self.consulta = consultas.agendar(self.pac, self.prof_a, proximo_dia_util(), "09:00")

    def tearDown(self):
        self._pasta.cleanup()

    def _novo_medico(self, login, nome, id_prof):
        autenticacao.cadastrar_usuario_por(
            self.admin["id"], nome, login, "senha123", papel=PAPEL_MEDICO, profissional_id=id_prof
        )
        return autenticacao.autenticar(login, "senha123")

    # ------------------------------------------------------------ pagamento
    def test_atendente_e_administrador_registram_pagamento(self):
        financeiro.registrar_pagamento(self.atendente["id"], self.consulta)
        self.assertEqual(consultas.obter(self.consulta)["pagamento_status"], "Pago")
        outra = consultas.agendar(self.pac, self.prof_a, proximo_dia_util(), "10:00")
        financeiro.registrar_pagamento(self.admin["id"], outra)
        self.assertEqual(consultas.obter(outra)["pagamento_status"], "Pago")

    def test_medico_nao_registra_pagamento(self):
        with self.assertRaises(ErroValidacao) as erro:
            financeiro.registrar_pagamento(self.medico_a["id"], self.consulta)
        self.assertIn("recepção", str(erro.exception))
        self.assertEqual(consultas.obter(self.consulta)["pagamento_status"], "Aguardando pagamento")

    def test_historico_guarda_quem_registrou_o_pagamento(self):
        financeiro.registrar_pagamento(self.atendente["id"], self.consulta)
        registro = financeiro.historico(self.admin["id"])[0]
        self.assertEqual(registro["tipo"], "pagamento")
        self.assertIn("@admin", registro["usuario_nome"])

    # ------------------------------------------------------------ confirmar
    def test_atendente_confirma_depois_do_pagamento(self):
        with self.assertRaises(ErroValidacao):  # ainda não pagou
            consultas.confirmar(self.atendente["id"], self.consulta)
        financeiro.registrar_pagamento(self.atendente["id"], self.consulta)
        consultas.confirmar(self.atendente["id"], self.consulta)
        self.assertEqual(consultas.obter(self.consulta)["situacao"], "Confirmada")

    def test_administrador_tambem_confirma(self):
        financeiro.registrar_pagamento(self.admin["id"], self.consulta)
        consultas.confirmar(self.admin["id"], self.consulta)
        self.assertEqual(consultas.obter(self.consulta)["situacao"], "Confirmada")

    def test_medico_e_desconhecido_nao_confirmam(self):
        financeiro.registrar_pagamento(self.atendente["id"], self.consulta)
        for quem in (self.medico_a["id"], None, 9999):
            with self.assertRaises(ErroValidacao):
                consultas.confirmar(quem, self.consulta)
        self.assertEqual(consultas.obter(self.consulta)["situacao"], "Agendada")

    # ------------------------------------------------------------ só o administrador
    def test_estorno_so_o_administrador(self):
        financeiro.registrar_pagamento(self.atendente["id"], self.consulta)
        for quem in (self.atendente, self.medico_a):
            with self.assertRaises(ErroValidacao):
                financeiro.desfazer_pagamento(quem["id"], self.consulta)
        financeiro.desfazer_pagamento(self.admin["id"], self.consulta)
        self.assertEqual(consultas.obter(self.consulta)["pagamento_status"], "Aguardando pagamento")

    def test_valores_so_o_administrador(self):
        esp = especialidades.listar("cardio")[0]
        for quem in (self.atendente, self.medico_a):
            with self.assertRaises(ErroValidacao):
                financeiro.alterar_valor_consulta(quem["id"], self.consulta, 5000)
            with self.assertRaises(ErroValidacao):
                financeiro.alterar_valor_especialidade(quem["id"], esp["id"], 5000)
        financeiro.alterar_valor_consulta(self.admin["id"], self.consulta, 5000)
        self.assertEqual(consultas.obter(self.consulta)["valor_centavos"], 5000)

    def test_painel_e_historico_so_o_administrador(self):
        for quem in (self.atendente, self.medico_a):
            for chamada in (financeiro.resumo, financeiro.historico, financeiro.listar_consultas):
                with self.assertRaises(ErroValidacao):
                    chamada(quem["id"])

    # ------------------------------------------------------------ consulta realizada
    def test_so_o_medico_dono_marca_como_realizada(self):
        for quem in (self.atendente, self.admin, self.medico_b):
            with self.assertRaises(ErroValidacao):
                consultas.marcar_realizada(quem["id"], self.consulta)
        self.assertEqual(consultas.obter(self.consulta)["situacao"], "Agendada")
        consultas.marcar_realizada(self.medico_a["id"], self.consulta)
        self.assertEqual(consultas.obter(self.consulta)["situacao"], "Realizada")

    def test_realizada_continua_respeitando_as_outras_regras(self):
        consultas.marcar_realizada(self.medico_a["id"], self.consulta)
        with self.assertRaises(ErroValidacao):  # já realizada
            consultas.marcar_realizada(self.medico_a["id"], self.consulta)
        cancelada = consultas.agendar(self.pac, self.prof_a, proximo_dia_util(), "11:00")
        consultas.cancelar(cancelada, "Imprevisto")
        with self.assertRaises(ErroValidacao):  # cancelada não vira realizada
            consultas.marcar_realizada(self.medico_a["id"], cancelada)

    def test_medico_desativado_nao_marca_realizada(self):
        autenticacao.atualizar_usuario(
            self.admin["id"], self.medico_a["id"], "Dra. Ana", "dra.ana", ativo=False,
            papel=PAPEL_MEDICO, profissional_id=self.prof_a,
        )
        with self.assertRaises(ErroValidacao):
            consultas.marcar_realizada(self.medico_a["id"], self.consulta)


if __name__ == "__main__":
    unittest.main()