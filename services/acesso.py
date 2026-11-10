"""A "portaria" do sistema: confere o papel de quem pede ANTES de chamar o serviço.

As funções de `pacientes`, `profissionais`, `especialidades`, `agenda` e `consultas` fazem as
regras de negócio (validar, gravar), mas não sabem QUEM está pedindo. Aqui cada ação ganha um
"cadeado": o primeiro parâmetro é sempre o `executor_id` (id do usuário logado), e o papel dele
é conferido NO BANCO. Se não puder, levanta ErroValidacao e nada é alterado.

REGRA DE OURO: as TELAS chamam estas funções (`acesso.cadastrar_paciente(...)`) e nunca as
funções cruas dos serviços (`pacientes.cadastrar(...)`). Os testes dos serviços e os scripts
continuam usando as cruas, que não conferem permissão.

Quem pode o quê:
  - Pacientes: cadastrar e alterar = Atendente e Administrador; desativar e excluir = Administrador.
  - Profissionais e especialidades: cadastrar, alterar, desativar e excluir = só Administrador.
  - Consultas: agendar, remarcar e cancelar = Atendente e Administrador.
  - Agenda (bloquear e liberar horários): Médico (só a sua) e Administrador.
"""
import functools

from services import agenda, autenticacao, consultas, especialidades, pacientes, profissionais
from services.autenticacao import PAPEL_ADMIN, PAPEL_ATENDENTE, PAPEL_MEDICO
from services.validacoes import ErroValidacao

RECEPCAO_E_ADMIN = (PAPEL_ATENDENTE, PAPEL_ADMIN)
SO_ADMIN = (PAPEL_ADMIN,)

MSG_PACIENTE = "Somente a recepção ou o administrador cadastram e alteram pacientes."
MSG_PACIENTE_ADMIN = "Somente o administrador desativa ou exclui pacientes."
MSG_PROFISSIONAL = "Somente o administrador gerencia profissionais."
MSG_ESPECIALIDADE = "Somente o administrador gerencia especialidades."
MSG_CONSULTA = "Somente a recepção ou o administrador agendam, remarcam e cancelam consultas."
MSG_AGENDA = "Somente o médico (na sua agenda) ou o administrador bloqueiam e liberam horários."
MSG_AGENDA_DE_OUTRO = "O médico só bloqueia ou libera a sua própria agenda."


def _guardar(funcao, papeis, mensagem):
    """Devolve uma versão da função que exige um dos `papeis` antes de executar."""

    @functools.wraps(funcao)
    def protegida(executor_id, *args, **kwargs):
        autenticacao.exigir_papel(executor_id, *papeis, mensagem=mensagem)
        return funcao(*args, **kwargs)

    return protegida


def _guardar_agenda(funcao):
    """Como `_guardar`, mas o Médico só mexe na agenda dele (o 1º argumento é o profissional)."""

    @functools.wraps(funcao)
    def protegida(executor_id, profissional_id, *args, **kwargs):
        quem = autenticacao.exigir_papel(
            executor_id, PAPEL_ADMIN, PAPEL_MEDICO, mensagem=MSG_AGENDA
        )
        if quem["papel"] == PAPEL_MEDICO and quem["profissional_id"] != profissional_id:
            raise ErroValidacao(MSG_AGENDA_DE_OUTRO)
        return funcao(profissional_id, *args, **kwargs)

    return protegida


# ----------------------------------------------------------------- pacientes
cadastrar_paciente = _guardar(pacientes.cadastrar, RECEPCAO_E_ADMIN, MSG_PACIENTE)
atualizar_paciente = _guardar(pacientes.atualizar, RECEPCAO_E_ADMIN, MSG_PACIENTE)
alternar_ativo_paciente = _guardar(pacientes.alternar_ativo, SO_ADMIN, MSG_PACIENTE_ADMIN)
excluir_paciente = _guardar(pacientes.excluir, SO_ADMIN, MSG_PACIENTE_ADMIN)

# ------------------------------------------------------------- profissionais
cadastrar_profissional = _guardar(profissionais.cadastrar, SO_ADMIN, MSG_PROFISSIONAL)
atualizar_profissional = _guardar(profissionais.atualizar, SO_ADMIN, MSG_PROFISSIONAL)
alternar_ativo_profissional = _guardar(profissionais.alternar_ativo, SO_ADMIN, MSG_PROFISSIONAL)
excluir_profissional = _guardar(profissionais.excluir, SO_ADMIN, MSG_PROFISSIONAL)

# ------------------------------------------------------------- especialidades
cadastrar_especialidade = _guardar(especialidades.cadastrar, SO_ADMIN, MSG_ESPECIALIDADE)
atualizar_especialidade = _guardar(especialidades.atualizar, SO_ADMIN, MSG_ESPECIALIDADE)
excluir_especialidade = _guardar(especialidades.excluir, SO_ADMIN, MSG_ESPECIALIDADE)

# ------------------------------------------------------------------ consultas
agendar_consulta = _guardar(consultas.agendar, RECEPCAO_E_ADMIN, MSG_CONSULTA)
alterar_consulta = _guardar(consultas.alterar_dados, RECEPCAO_E_ADMIN, MSG_CONSULTA)
cancelar_consulta = _guardar(consultas.cancelar, RECEPCAO_E_ADMIN, MSG_CONSULTA)

# --------------------------------------------------------------------- agenda
bloquear_horario = _guardar_agenda(agenda.bloquear_horario)
liberar_horario = _guardar_agenda(agenda.liberar_horario)
bloquear_dia = _guardar_agenda(agenda.bloquear_dia)
liberar_dia = _guardar_agenda(agenda.liberar_dia)