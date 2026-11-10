"""Quais telas cada papel enxerga no menu (regra pura, sem Tkinter: fácil de testar).

O menu só ESCONDE o que a pessoa não deve usar. Quem de fato barra é o back-end
(`autenticacao.exigir_papel` e a portaria em `services/acesso.py`), que confere o papel
no banco. A primeira tela da lista é a que abre logo depois do login.
"""
from services.autenticacao import PAPEL_ADMIN, PAPEL_ATENDENTE, PAPEL_MEDICO

CONSULTAS = "consultas"
AGENDA = "agenda"
PACIENTES = "pacientes"
PROFISSIONAIS = "profissionais"
ESPECIALIDADES = "especialidades"
FINANCEIRO = "financeiro"
PRONTUARIO = "prontuario"
USUARIOS = "usuarios"

MENU_POR_PAPEL = {
    PAPEL_ADMIN: (
        CONSULTAS, AGENDA, PACIENTES, PROFISSIONAIS, ESPECIALIDADES, FINANCEIRO, USUARIOS,
    ),
    PAPEL_ATENDENTE: (CONSULTAS, AGENDA, PACIENTES),
    PAPEL_MEDICO: (CONSULTAS, AGENDA, PRONTUARIO),
}

# Ações que mudam o que aparece nas telas (botões). O back-end barra de qualquer jeito.
DESATIVAR_EXCLUIR_PACIENTE = "desativar_excluir_paciente"
GERIR_CONSULTAS = "gerir_consultas"  # agendar, remarcar, cancelar e confirmar
ATENDER = "atender"  # marcar como realizada, atestado e receituário
BLOQUEAR_AGENDA = "bloquear_agenda"

QUEM_PODE = {
    DESATIVAR_EXCLUIR_PACIENTE: (PAPEL_ADMIN,),
    GERIR_CONSULTAS: (PAPEL_ATENDENTE, PAPEL_ADMIN),
    ATENDER: (PAPEL_MEDICO,),
    BLOQUEAR_AGENDA: (PAPEL_ADMIN, PAPEL_MEDICO),
}


def pode(papel, acao):
    """Diz se o papel deve ver o botão daquela ação (False para papel ou ação desconhecidos)."""
    return papel in QUEM_PODE.get(acao, ())


def telas_do_papel(papel):
    """Nomes das telas do menu para o papel, na ordem em que aparecem (vazio se desconhecido)."""
    return MENU_POR_PAPEL.get(papel, ())


def tela_inicial(papel):
    """Tela que abre logo depois do login (None se o papel for desconhecido)."""
    telas = telas_do_papel(papel)
    return telas[0] if telas else None