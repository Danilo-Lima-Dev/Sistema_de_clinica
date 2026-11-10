"""O "fiscal da portaria": as TELAS nunca podem chamar as funções cruas dos serviços.

Quem barra o acesso por papel é `services/acesso.py`. Se uma tela chamar, por exemplo,
`pacientes.cadastrar(...)` direto, ela passa por cima da portaria e qualquer usuário
consegue fazer a ação. Este teste lê os arquivos de `ui/` e falha se achar isso.
Execute com:  python -m unittest discover -s tests
"""
import re
import unittest
from pathlib import Path

PASTA_UI = Path(__file__).resolve().parent.parent / "ui"

# funções que alteram dados e por isso só podem ser chamadas pela portaria (acesso.xxx)
PROIBIDAS = re.compile(
    r"\b(?:"
    r"pacientes\.(?:cadastrar|atualizar|excluir|alternar_ativo)"
    r"|profissionais\.(?:cadastrar|atualizar|excluir|alternar_ativo)"
    r"|especialidades\.(?:cadastrar|atualizar|excluir)"
    r"|agenda\.(?:bloquear_horario|liberar_horario|bloquear_dia|liberar_dia)"
    r"|consultas\.(?:agendar|alterar_dados|cancelar)"
    r")\("
)


class TestUiUsaPortaria(unittest.TestCase):
    def test_ha_telas_para_conferir(self):
        self.assertTrue(list(PASTA_UI.glob("*.py")))

    def test_nenhuma_tela_pula_a_portaria(self):
        problemas = []
        for arquivo in sorted(PASTA_UI.glob("*.py")):
            for numero, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
                if linha.lstrip().startswith("#"):
                    continue
                if PROIBIDAS.search(linha):
                    problemas.append(f"{arquivo.name}:{numero}: {linha.strip()}")
        self.assertEqual(
            problemas, [],
            "Estas telas chamam o serviço direto; use `acesso.<funcao>(usuario['id'], ...)`:\n"
            + "\n".join(problemas),
        )

    def test_o_fiscal_realmente_pega_uma_chamada_crua(self):
        self.assertTrue(PROIBIDAS.search("    pacientes.cadastrar(*dados)"))
        self.assertTrue(PROIBIDAS.search("consultas.cancelar(id, motivo)"))
        self.assertFalse(PROIBIDAS.search("acesso.cadastrar_paciente(uid, *dados)"))
        self.assertFalse(PROIBIDAS.search("pacientes.obter(id)"))  # leitura pode


if __name__ == "__main__":
    unittest.main()