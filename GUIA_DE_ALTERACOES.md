# Guia das alterações – Sistema da Clínica (11 requisitos)

## Como aplicar (jeito mais simples)
1. Faça backup da sua pasta atual (e do `clinica.db`).
2. Extraia `sistema_de_clinica_ajustado.zip` e **copie tudo por cima** do seu projeto (substitui os arquivos alterados e acrescenta os novos).
3. Instale a biblioteca nova: `pip install -r requirements.txt` (acrescentou `phonenumbers`).
4. Rode `python main.py`. O banco antigo é migrado sozinho (colunas novas, nada se perde).
5. Testes: `python -m unittest discover -s tests -v` (87 testes passam).

Logins: `admin / admin123` (comum) e `super / super123` (super usuário – o único que vê **Financeiro** e **Usuários**). Troque a senha do super.

> O seu repositório tinha o `super_usuario.patch` ainda **não aplicado**. Como o item 4 depende do super usuário, apliquei esse patch (tela Usuários, coluna `superusuario`). Você pode apagar os 3 arquivos `.patch`.

## Arquivos NOVOS (copie para a mesma pasta)
| Arquivo | O que é | Item |
|---|---|---|
| `services/agenda.py` | horários disponível/reservado/indisponível, bloqueios | 1 |
| `services/especialidades.py` | cadastro, valor, exclusão segura, busca | 2, 9, 10 |
| `services/financeiro.py` | valores, pagamento, painel, histórico (só super) | 4, 5 |
| `services/atestado.py` | atestado A4 para imprimir | 6 |
| `services/receituario.py` | receituário A4 para imprimir (extra) | extra |
| `services/documentos.py` | salva atestados/receituários no banco, por paciente; só super lê (extra) | extra |
| `ui/tela_prontuario.py` | tela Prontuário (só super usuário) | extra |
| `ui/tela_agenda.py` | tela Agenda | 1 |
| `ui/tela_especialidades.py` | tela Especialidades | 2, 9, 10 |
| `ui/tela_financeiro.py` | tela Financeiro (3 abas) | 4 |
| `ui/dialogos.py` | cadastro rápido de paciente + diálogos do atestado e do receituário | 6, 11, extra |
| `ui/tela_usuarios.py` | tela Usuários (do patch) | 4 |
| `tests/test_novos_requisitos.py` | testes novos | todos |

## Arquivos ALTERADOS e o que mudou
| Arquivo | Alteração |
|---|---|
| `database.py` | colunas novas (`especialidade.valor_consulta`, `paciente.ativo`, financeiro na `consulta`), tabelas `bloqueio_agenda` e `financeiro_historico`, situação **Confirmada**, gatilho "só confirma se pago", função `sem_acento` para buscas, migração de banco antigo |
| `services/validacoes.py` | e-mail mais rígido, telefone (DDD, celular/fixo, repetidos/sequenciais, `phonenumbers`), máscara `(86) 99999-9999`, busca sem acento, valores em R$ |
| `services/consultas.py` | agenda indisponível barra agendamento, paciente desativado barrado, valor + "Aguardando pagamento" ao agendar, nova função `confirmar()`, busca sem acento |
| `services/pacientes.py` | validação de telefone/e-mail, `alternar_ativo()` (desativar), `listar(... incluir_inativos, limite)` com busca por nome/CPF/telefone |
| `services/profissionais.py` | telefone validado, busca sem acento, `limite/offset`, traz o valor da especialidade |
| `services/comprovante.py` | valor e status **PAGO / AGUARDANDO PAGAMENTO** |
| `services/autenticacao.py` | `exigir_superusuario()` reutilizável |
| `ui/app.py` | menu com Especialidades, Agenda, Financeiro e Prontuário (super) |
| `ui/componentes.py` | `barra_busca` (tempo real), `CampoComSugestoes` (autocompletar), `GradeHorarios`, erros inline |
| `ui/tema.py` | cores dos horários e `LOCAL_EMISSAO` (**troque para sua cidade**) |
| `ui/tela_consultas.py` | botão **Gerar receituário** (ao lado de Gerar atestado), busca de médico/paciente, valor, horários, atalho "Cadastrar novo paciente", **Confirmar consulta**, **Gerar atestado**, colunas Pagamento/Valor |
| `ui/tela_pacientes.py` / `tela_profissionais.py` | máscara e erro de telefone/e-mail, busca em tempo real, Desativar/Reativar, "Tem certeza?" |
| `requirements.txt` | + `phonenumbers` |
| `tests/test_clinica.py` | só 3 ajustes: telefone de teste sequencial trocado e datas de fim de semana movidas para dias úteis |

## Onde está cada item
1. **Agenda**: `services/agenda.py` (expediente nas constantes do topo) + menu *Agenda* e grade verde/laranja/cinza em *Consultas*.
2. **Valor**: menu *Especialidades* (campo só habilitado ao super) e `services/financeiro.py`.
3. **Comprovante**: botão *Imprimir comprovante* já existia; agora traz status e valor.
4. **Financeiro**: menu *Financeiro* → abas Pagamentos, Valores por especialidade, Histórico. Permissão conferida no back-end.
5. **Confirmação**: botão *Confirmar consulta*; recusa em `consultas.confirmar()` e no banco.
6. **Atestado**: botão *Gerar atestado* (dias obrigatório, CID opcional).
7/8. **E-mail/telefone**: `services/validacoes.py`; erro aparece abaixo do campo e o back-end confere de novo.
9. **Exclusões**: confirmação "Tem certeza?"; especialidade e paciente com vínculo não excluem; paciente é desativado.
10. **Busca**: Pacientes, Profissionais, Especialidades e Consultas filtram enquanto digita.
11. **Agendamento**: autocompletar (10 por vez), valor e horários do médico, atalho de novo paciente, desativados fora.

## Decisões que tomei (ajuste se quiser)
- Expediente: 08:00–18:00, seg–sex, blocos de 30 min (`services/agenda.py`).
- Consultas antigas migradas ficam "Aguardando pagamento" com valor R$ 0,00; o super ajusta no Financeiro.
- *Marcar como realizada* continua aceitando consulta não confirmada. Para exigir confirmação, em `consultas.marcar_realizada` troque a checagem por `if atual["situacao"] != "Confirmada": raise ErroValidacao(...)`.
- O OTP por SMS/WhatsApp (opcional no item 8) **não foi feito**: o sistema não tem autoatendimento do paciente.
- Se `phonenumbers` não estiver instalado, o sistema usa regras próprias (DDD, 9 no celular, 2–5 no fixo).
- Testei os serviços e a interface (com tela virtual); não testei a impressão real em navegador.

## Extra: Receituário
- Selecione uma consulta na tela *Consultas* e clique em **Gerar receituário** (o botão **Gerar atestado** fica ao lado; os dois só ficam desligados em consulta cancelada).
- Nome, CPF e nascimento do paciente e nome/CRM/especialidade do médico vêm da consulta; você digita só a prescrição (várias linhas) e o local.
- Abre uma folha A4 no navegador já com a janela de impressão. Código em `services/receituario.py`; diálogo em `ui/dialogos.py` (`DialogoReceituario`).

## Extra: documentos salvos no banco (só o super usuário vê)
- Todo **atestado** e **receituário** gerado na tela *Consultas* é salvo automaticamente na nova tabela `documento_emitido` (criada sozinha em bancos antigos): paciente, consulta, tipo, data/hora, médico, quem emitiu, texto e a página para reimprimir.
- Menu **Prontuário** (só super usuário): busque o paciente, veja a lista de documentos, o texto ao lado e use **Reimprimir**.
- A permissão é conferida no back-end (`services/documentos.py`): usuário comum não consegue listar nem abrir, mesmo chamando o código direto.
- `TelaConsultas` agora recebe o usuário logado (`ui/app.py` já faz isso) para registrar quem emitiu.
- Não salvei o comprovante (ele é regerado a qualquer momento a partir da consulta).

## Ajuste: lista de consultas maior (tela Consultas)
- Em telas de ~768 px o formulário ocupava quase tudo e a lista de consultas ficava sem espaço. Em `ui/tela_consultas.py`:
  - a tela agora **rola** (`CTkScrollableFrame`) com a roda do mouse;
  - a lista mostra **12 linhas** (`criar_tabela(..., altura=12)`; antes 5);
  - novo botão **Ocultar formulário / Mostrar formulário** no topo da lista; ao selecionar uma consulta o formulário reabre sozinho para edição.
- Para mudar o tamanho da lista, altere `altura=12` em `_montar_lista`.
