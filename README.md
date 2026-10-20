# Sistema de Clínica

Trabalho prático de Desenvolvimento Rápido de Aplicações em Python.
Aplicação desktop (CustomTkinter) com banco de dados SQLite e tela de login.

## Estado atual

| Tela | Situação |
| --- | --- |
| Login | Funcionando: usuário e senha (senha guardada com hash PBKDF2); cria o usuário `admin` na primeira execução |
| Pacientes | Funcionando: cadastrar, listar, buscar, alterar e excluir |
| Profissionais | Funcionando: cadastrar, listar, buscar por nome/especialidade, alterar, inativar/ativar e excluir |
| Consultas | Funcionando: agendar, listar, filtrar por situação, alterar/remarcar, marcar como realizada, cancelar e imprimir o comprovante de agendamento (bobina 80 mm ou 58 mm) |

O banco é criado com as 5 tabelas do modelo (`usuario`, `especialidade`, `paciente`, `profissional`, `consulta`)
e já vem com as especialidades iniciais: Clínica Geral, Pediatria, Cardiologia, Dermatologia e Ortopedia.

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

> O repositório já inclui um `clinica.db` com alguns registros de exemplo.
> Para começar do zero, feche o programa e apague o arquivo `clinica.db`: ele é recriado
> vazio (só com o `admin` e as especialidades iniciais) na próxima execução.

## Login e usuários

- O login não diferencia maiúsculas de minúsculas; a senha deve ter pelo menos 6 caracteres.
- Depois de 5 tentativas erradas na tela de login, o programa fecha.
- Ainda não existe tela para cadastrar usuários nem função para trocar a senha de um usuário já criado.
  Para cadastrar outro usuário, rode na pasta do projeto (trocando nome, login e senha):

```bash
python -c "import database; from services import autenticacao; database.criar_tabelas(); autenticacao.cadastrar_usuario('Maria Souza', 'maria', 'senha123')"
```

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
| `database.py` | Conexão com o SQLite e criação das 5 tabelas (`usuario`, `especialidade`, `paciente`, `profissional`, `consulta`). |
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
| `ui/app.py` | Janela principal: login e, depois, menu lateral em cartões + telas com atualização automática. |
| `ui/tela_pacientes.py` | Tela de pacientes: formulário, busca, tabela, mensagens e máscaras de digitação. |
| `ui/tela_profissionais.py` | Tela de profissionais: formulário, seleção de especialidades, busca, tabela e inativação/exclusão. |
| `ui/tela_consultas.py` | Tela de consultas: agendamento com pacientes/médicos cadastrados, filtros por situação, remarcação, cancelamento e botão "Imprimir comprovante". |
| `ui/telas_prototipo.py` | Protótipos antigos de Profissionais e Consultas. Não são mais usados pelo sistema (as telas reais estão em `tela_profissionais.py` e `tela_consultas.py`). |
| `cli/` | Versão antiga em terminal (só pacientes). Não é chamada pelo `main.py` e não passa pelo login. Ver "Versão em terminal". |
| `tests/test_clinica.py` | Testes automáticos das validações, das regras e da persistência dos dados de todas as entidades. |
| `DOCUMENTOS/Relatorio_Sistema_Clinica_Equipe.docx` | Relatório do sistema produzido pela equipe. |
| `__init__.py` (em `services/`, `ui/` e `cli/`) | Arquivos vazios que permitem importar as pastas como pacotes. |

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
- CPF digitado só com números (11 dígitos) e único no sistema (RN02 e RN06).
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
- O mesmo profissional não pode ter duas consultas ativas no mesmo dia e horário de início; consultas canceladas não bloqueiam o horário (RN01).
- Cada consulta tem duração fixa de 30 minutos: o horário de término é calculado automaticamente.
- Consultas canceladas ou já realizadas não podem ser alteradas. Uma consulta realizada não pode ser cancelada, e uma cancelada não pode ser marcada como realizada.
- Ao selecionar uma consulta na tabela aparece o botão **Imprimir comprovante**, com os dados do paciente (CPF parcialmente oculto, ex.: `529.***.***-25`), do profissional, a especialidade, a data e o horário. Escolha o papel (80 mm ou 58 mm); o comprovante abre no navegador já com a janela de impressão, onde se escolhe a impressora térmica (em "Mais definições", deixe as margens em "Nenhuma" e desmarque cabeçalhos e rodapés).
- Consultas não são excluídas, e sim canceladas (com motivo opcional), para manter o histórico (RN07).

## Modo de teste do CPF

Por enquanto, a conferência dos dígitos verificadores do CPF está **desativada**, para permitir testes com CPFs fictícios (o sistema só exige 11 números e não aceita CPF repetido).
Para ativá-la de novo, altere em `services/pacientes.py`:

```python
VALIDAR_CPF = True
```

Os dados de teste devem ser sempre fictícios.

## Versão em terminal

A pasta `cli/` guarda uma versão antiga do sistema para o terminal, só com o cadastro de pacientes
(Profissionais e Consultas aparecem como "em desenvolvimento"). Ela usa as mesmas regras e o mesmo banco,
mas não passa pela tela de login. Para abri-la, na pasta do projeto:

```bash
python -c "from cli.app import executar; executar()"
```