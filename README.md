# Sistema de Clínica

Trabalho prático de Desenvolvimento Rápido de Aplicações em Python.
Aplicação desktop (CustomTkinter) com banco de dados SQLite e tela de login.

## Estado atual

| Tela | Quem usa | Situação |
| --- | --- | --- |
| Login | todos | Funcionando: usuário e senha (senha guardada com hash PBKDF2); cria os usuários padrão na primeira execução |
| Pacientes | Atendente, Administrador | Cadastrar, listar, buscar, alterar, desativar e excluir |
| Profissionais | Administrador | Cadastrar, listar, buscar por nome/especialidade, alterar, inativar/ativar e excluir |
| Especialidades | Administrador | Cadastrar, valor da consulta, buscar em tempo real e excluir (se não houver vínculos) |
| Consultas | Atendente, Administrador, Médico | Agendar, listar, filtrar, remarcar, cancelar, confirmar (após o pagamento), marcar como realizada (médico) e imprimir o comprovante (bobina 80 mm ou 58 mm) |
| Agenda | Atendente, Administrador, Médico | Horários do médico (disponível, reservado, indisponível) e bloqueio de horário/dia |
| Financeiro | Administrador | Valores, pagamentos, painel recebido/pendente e histórico |
| Documentos / Prontuário | Atendente (lê e entrega 2ª via), Médico (emite e reimprime) | Atestado e receituário guardados por paciente |
| Histórico clínico | Médico | Anotações por paciente; só o autor altera, com versões anteriores guardadas |
| Usuários | Administrador | Cadastrar e alterar usuários, perfil (papel) e profissional do médico |

O banco SQLite (`clinica.db`) é criado automaticamente, com as tabelas do modelo (`usuario`, `especialidade`, `paciente`,
`profissional`, `consulta`, `bloqueio_agenda`, `financeiro_historico`, `documento_emitido`, `entrega_documento`,
`historico_clinico` e `historico_clinico_revisao`) e já vem com as especialidades iniciais: Clínica Geral, Pediatria, Cardiologia, Dermatologia e Ortopedia.

## Requisitos

- Python 3.9 ou superior
- Tkinter (já vem com o Python no Windows e no macOS)
  - Linux (Debian/Ubuntu): `sudo apt install python3-tk`
- CustomTkinter (visual moderno). Instale uma vez com:

```bash
pip install -r requirements.txt
```

## Como executar

```bash
python main.py
```

Na primeira execução o arquivo `clinica.db` é criado automaticamente na pasta do projeto,
junto com o usuário padrão do login: **usuário `admin`, senha `admin123`**.

> O repositório já inclui um `clinica.db` preenchido com dados de demonstração, todos fictícios (nomes inventados, e-mails `@exemplo.com` e CPFs gerados só para teste). Os logins de teste estão na seção *Papéis, histórico clínico e dados de teste*.
> Para começar do zero, feche o programa e apague o arquivo `clinica.db`: ele é recriado
> vazio (só com os usuários padrão e as especialidades iniciais) na próxima execução.

## Login e usuários

- O login não diferencia maiúsculas de minúsculas; a senha deve ter pelo menos 6 caracteres.
- Depois de 5 tentativas erradas na tela de login, o programa fecha.
- Existem três papéis: **Administrador**, **Atendente** (recepção) e **Médico** (veja a seção seguinte).
- Usuários padrão criados na primeira execução: `super` / `super123` (Administrador) e `admin` / `admin123` (Atendente).
  Troque essas senhas no primeiro acesso, em Usuários.
- Na tela **Usuários**, o Administrador cadastra usuários e, ao selecionar um da lista, altera nome, login, perfil,
  profissional do médico e situação (ativo/inativo), ou troca a senha (senha em branco mantém a atual). Também pode **excluir** um usuário (com confirmação).
- Regras: só o Administrador gerencia usuários (conferido no banco a cada ação); não é possível desativar nem excluir o próprio
  usuário, nem deixar o sistema sem nenhum Administrador ativo.
- Bancos antigos são migrados automaticamente na próxima execução.

## Papéis, histórico clínico e dados de teste

- **Papéis** (campo *Perfil* na tela Usuários): **Administrador** (gerencia tudo, menos dados clínicos),
  **Atendente** (recepção: pacientes, consultas, pagamento; só lê documentos e entrega a 2ª via com registro)
  e **Médico** (ligado a um profissional; atende, emite atestado/receituário e usa o histórico clínico).
  Atendente e Administrador **não emitem** atestado nem receituário.
- **Histórico clínico por paciente** (menu *Histórico clínico*, `services/historico_clinico.py`): só o papel
  Médico lê e escreve; só o médico que escreveu uma anotação a altera, e a versão anterior fica guardada
  ("Versões anteriores"). Nada é apagado; paciente com histórico não pode ser excluído (use *Desativar*).
- **Validação na alteração de dados**: nomes (2+ letras, só letras/espaço/`'`/`.`/`-`, até 100), registro profissional
  (4 a 30 caracteres, com número), login (3 a 30: letras, números, `.`, `-`, `_`), senha (6 a 128, não igual ao login, sem espaço nas
  pontas), observações da consulta (até 500). Ao salvar uma alteração, as telas dizem *"Nenhuma alteração para salvar"* se nada mudou
  e pedem confirmação. Consulta paga ou confirmada não troca de paciente nem de médico.
- **Dados fictícios para teste**: `python popular_dados_teste.py` (num banco novo) cria pacientes, profissionais, consultas, documentos
  e anotações de exemplo. Logins: `super`/`super123` (Administrador); `admin`/`admin123` e `recepcao`/`recepcao123` (Atendente);
  `helena`, `rafael` e `luiza` / `medico123` (Médico).

## Personalizar a aparência

Nome do programa, frase de apresentação, cores, fonte e modo claro/escuro ficam todos em `ui/tema.py`.
No menu lateral do sistema há também uma chave para alternar entre o modo claro e o escuro.

## Como testar

```bash
python -m unittest discover -s tests -v
```

## Estrutura do projeto

| Arquivo | Função |
| --- | --- |
| `main.py` | Ponto de entrada: cria o banco (se não existir), cria o usuário padrão e abre a janela no login. |
| `requirements.txt` | Bibliotecas externas necessárias (CustomTkinter). |
| `database.py` | Conexão com o SQLite, criação e migração das 11 tabelas (`usuario`, `especialidade`, `paciente`, `profissional`, `consulta`, `bloqueio_agenda`, `financeiro_historico`, `documento_emitido`, `entrega_documento`, `historico_clinico` e `historico_clinico_revisao`), gatilhos e índice único. |
| `clinica.db` | Banco de dados, criado automaticamente na primeira execução (o repositório traz um com dados de exemplo). |
| `services/validacoes.py` | Funções de apoio: validação e formatação de CPF, datas, horários, telefone e e-mail. |
| `services/pacientes.py` | Regras de negócio e SQL do cadastro de pacientes (cadastrar, listar, buscar, alterar, excluir). |
| `services/profissionais.py` | Regras de negócio e SQL dos profissionais (cadastrar, listar, buscar, alterar, inativar, excluir). |
| `services/consultas.py` | Regras de negócio e SQL dos agendamentos (agendar, alterar/remarcar, cancelar, registrar realização, prevenção de conflito). |
| `services/comprovante.py` | Comprovante de agendamento para impressora térmica: monta os dados, o texto e a página HTML (80 mm ou 58 mm) e abre a janela de impressão. |
| `services/autenticacao.py` | Login: usuários, senha com hash (PBKDF2) e conferência. |
| `ui/tema.py` | Nome do programa, cores, fontes e modo claro/escuro (personalização visual). |
| `ui/componentes.py` | Peças visuais reutilizadas: cartão, cabeçalho, campo de texto, combobox, botão e tabela. |
| `ui/tela_login.py` | Tela de login. |
| `ui/tela_usuarios.py` | Tela "Usuários" (só para o Administrador): cadastrar, alterar e excluir usuários (nome, login, senha, perfil, profissional do médico e situação). |
| `services/historico_clinico.py`, `ui/tela_historico.py` | Histórico clínico por paciente (só Médico). |
| `popular_dados_teste.py` | Carrega dados fictícios de teste. |
| `ui/app.py` | Janela principal: login e, depois, menu lateral em cartões + telas com atualização automática. |
| `ui/tela_pacientes.py` | Tela de pacientes: formulário, busca, tabela, mensagens e máscaras de digitação. |
| `ui/tela_profissionais.py` | Tela de profissionais: formulário, seleção de especialidades, busca, tabela e inativação/exclusão. |
| `ui/tela_consultas.py` | Tela de consultas: agendamento com pacientes/médicos cadastrados, filtros por situação, remarcação, cancelamento e botão "Imprimir comprovante". |
| `services/agenda.py`, `services/especialidades.py`, `services/financeiro.py` | Agenda do médico, especialidades com valor da consulta e financeiro (pagamentos e histórico). |
| `services/atestado.py`, `services/receituario.py`, `services/documentos.py` | Atestado e receituário (A4) e documentos emitidos, guardados por paciente. |
| `tests/` | 173 testes automáticos: validações, regras de negócio, persistência, permissões por papel, documentos, pagamento e histórico clínico. |
| `DOCUMENTOS/Relatorio_Sistema_Clinica_Equipe.docx` | Relatório final da equipe (entregue junto com o pacote). |
| `__init__.py` (em `services/` e `ui/`) | Arquivos vazios que permitem importar as pastas como pacotes. |

## Cancelamento no lugar de exclusão (consultas)

Consultas **não são excluídas**: são **canceladas**, com motivo opcional. A decisão é deliberada: a consulta é ligada a
pagamento (financeiro), documentos emitidos e histórico clínico, e esses registros precisam continuar rastreáveis. Cancelar
libera o horário do profissional, mantém o histórico e permite auditar quem fez o quê. Já pacientes e profissionais
podem ser excluídos quando não há vínculos; havendo vínculos, o sistema oferece **desativar**.

## Organização em camadas

```
main.py → ui/ (telas) → services/ (regras) → database.py → clinica.db
```

- **ui/**: só cuida do que aparece na tela e não escreve SQL.
- **services/**: concentra as validações e as regras de negócio.
- **database.py**: concentra o acesso ao banco.

Essa separação permite alterar o visual sem quebrar as regras (e o contrário), e facilita a divisão do trabalho entre os integrantes.

## Regras já aplicadas

Os códigos entre parênteses (RN01 a RN07) são os mesmos do relatório, seção 3.

**Pacientes**

- Nome, CPF e data de nascimento obrigatórios (RN02).
- CPF digitado só com números (11 dígitos), com os dígitos verificadores conferidos, e único no sistema (RN02 e RN06).
- Data de nascimento no formato DD/MM/AAAA e não pode ser futura (RN05).
- Paciente com consultas vinculadas não pode ser excluído (RN04).

**Profissionais**

- Nome, registro profissional (CRM, CREFITO etc.) e especialidade obrigatórios (RN02).
- Registro profissional único no sistema (RN06).
- Telefone, quando informado, com DDD (10 ou 11 dígitos).
- Profissional com consultas vinculadas não pode ser excluído; nesse caso use "Inativar" para impedir novos agendamentos sem perder o histórico (RN04).

**Consultas**

- Paciente, profissional, data e horário obrigatórios; o horário vai no formato HH:MM (RN02).
- Não é possível agendar com profissional inativo.
- Não é possível agendar em data e hora que já passaram (RN05).
- **Sem conflito de horário (RN01):** cada consulta dura 30 minutos, então o mesmo profissional não pode ter duas consultas ativas **sobrepostas** (09:00 e 09:15 conflitam; 09:30 é aceito). A sobreposição é barrada no serviço, e o banco também barra horário idêntico (índice único). Consultas canceladas liberam o horário.
- Cada consulta tem duração fixa de 30 minutos: o horário de término é calculado automaticamente.
- Consultas canceladas ou já realizadas não podem ser alteradas. Uma consulta realizada não pode ser cancelada, e uma cancelada não pode ser marcada como realizada.
- Ao selecionar uma consulta na tabela aparece o botão **Imprimir comprovante**, com os dados do paciente (CPF parcialmente oculto, ex.: `529.***.***-25`), do profissional, a especialidade, a data e o horário. Escolha o papel (80 mm ou 58 mm); o comprovante abre no navegador já com a janela de impressão, onde se escolhe a impressora térmica (em "Mais definições", deixe as margens em "Nenhuma" e desmarque cabeçalhos e rodapés).
- Consultas não são excluídas, e sim canceladas (com motivo opcional), para manter o histórico (RN07).

## Novidades (requisitos de out/2026)

- **Agenda** (`services/agenda.py`, `ui/tela_agenda.py`): expediente padrão 08:00–18:00, segunda a sexta, horários de 30 min (edite as constantes no topo de `services/agenda.py`). Horário indisponível não aceita agendamento.
- **Valor por especialidade**: coluna `valor_consulta` (em centavos). Só o Administrador altera; conferido no back-end.
- **Financeiro** (`services/financeiro.py`, `ui/tela_financeiro.py`): pagamento, painel, filtros e histórico (quem e quando).
- **Confirmação só após pagamento**: a consulta nasce *Agendada* + *Aguardando pagamento*; `consultas.confirmar()` e um gatilho no banco recusam confirmar sem pagamento.
- **Comprovante** agora mostra valor e status do pagamento.
- **Atestado médico** (`services/atestado.py`): paciente e médico automáticos; dias e CID digitados; local padrão em `ui/tema.py` (`LOCAL_EMISSAO`).
- **Validações** de e-mail e telefone (máscara `(86) 99999-9999`, DDD existente, bloqueio de números repetidos/sequenciais, biblioteca `phonenumbers`).
- **Exclusões seguras**: especialidade com médicos/consultas não exclui; paciente com consultas é *desativado* (exclusão lógica) e some do agendamento.
- **Buscas** em tempo real, sem acento e parciais, com "Nenhum resultado encontrado" e "Limpar busca"; no agendamento há autocompletar (10 por vez) e atalho para cadastrar paciente.
- Bancos antigos são migrados automaticamente na primeira execução.
- **Receituário médico** (`services/receituario.py`): botão *Gerar receituário* na tela Consultas; dados do paciente e do médico automáticos, prescrição digitada, impressão em A4.
- **Documentos salvos** (`services/documentos.py`, `ui/tela_prontuario.py`): atestados e receituários emitidos ficam no banco por paciente; o Médico emite e reimprime os seus (menu *Prontuário*) e o Atendente só lê e entrega a 2ª via, com registro.
