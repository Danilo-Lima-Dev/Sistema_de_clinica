# Sistema de Clínica

Trabalho prático de Desenvolvimento Rápido de Aplicações em Python.
Aplicação desktop (CustomTkinter) com banco de dados SQLite.

## Estado atual

| Tela | Situação |
| --- | --- |
| Pacientes | Funcionando: cadastrar, listar, buscar, alterar e excluir |
| Profissionais | Funcionando: cadastrar, listar, buscar por nome/especialidade, alterar, inativar/ativar e excluir |
| Consultas | Funcionando: agendar, listar, filtrar por situação, alterar/remarcar, marcar como realizada e cancelar |

O banco já é criado com as 4 tabelas do modelo (`especialidade`, `paciente`, `profissional`, `consulta`).

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
junto com o usuário padrão do login: **usuário `admin`, senha `admin123`** (troque depois).

## Personalizar a aparência

Nome do programa, cores, fontes e modo claro/escuro ficam todos em `ui/tema.py`.
Para começar do zero, feche o programa e apague o arquivo `clinica.db`.

## Como testar

```bash
python -m unittest discover -s tests -v
```

## Estrutura do projeto

| Arquivo | Função |
| --- | --- |
| `main.py` | Ponto de entrada: cria o banco (se não existir) e abre a janela. |
| `database.py` | Conexão com o SQLite e criação das 4 tabelas (`especialidade`, `paciente`, `profissional`, `consulta`). |
| `clinica.db` | Banco de dados, criado automaticamente na primeira execução. |
| `services/validacoes.py` | Funções de apoio: validação e formatação de CPF, datas, horários, telefone e e-mail. |
| `services/pacientes.py` | Regras de negócio e SQL do cadastro de pacientes (cadastrar, listar, buscar, alterar, excluir). |
| `services/profissionais.py` | Regras de negócio e SQL dos profissionais (cadastrar, listar, buscar, alterar, inativar, excluir). |
| `services/consultas.py` | Regras de negócio e SQL dos agendamentos (agendar, remarcar, cancelar, registrar realização, prevenção de conflito). |
| `services/autenticacao.py` | Login: usuários, senha com hash (PBKDF2) e conferência. |
| `ui/tema.py` | Nome do programa, cores, fontes e modo claro/escuro (personalização visual). |
| `ui/componentes.py` | Peças visuais reutilizadas: cartão, cabeçalho, campo de texto, combobox, botão e tabela. |
| `ui/tela_login.py` | Tela de login. |
| `ui/app.py` | Janela principal: login e, depois, menu lateral em cartões + telas com atualização automática. |
| `ui/tela_pacientes.py` | Tela de pacientes: formulário, busca, tabela, mensagens e máscaras de digitação. |
| `ui/tela_profissionais.py` | Tela de profissionais: formulário, seleção de especialidades, busca, tabela e inativação/exclusão. |
| `ui/tela_consultas.py` | Tela de consultas: agendamento com pacientes/médicos cadastrados, filtros por situação, remarcação e cancelamento. |
| `tests/test_clinica.py` | Testes automáticos das validações, das regras e da persistência dos dados de todas as entidades. |
| `__init__.py` (em `services/` e `ui/`) | Arquivos vazios que permitem importar as pastas como pacotes. |


## Organização em camadas

```
main.py → ui/ (telas) → services/ (regras) → database.py → clinica.db
```

- **ui/**: só cuida do que aparece na tela e não escreve SQL.
- **services/**: concentra as validações e as regras de negócio.
- **database.py**: concentra o acesso ao banco.

Essa separação permite alterar o visual sem quebrar as regras (e o contrário), e facilita a divisão do trabalho entre os integrantes.

## Regras já aplicadas

- Nome, CPF e data de nascimento obrigatórios (RN01).
- CPF digitado só com números (11 dígitos) e único (RN02).
- Data de nascimento no formato DD/MM/AAAA e não pode ser futura (RN03).
- Paciente com consultas vinculadas não pode ser excluído (RN12).

## Modo de teste do CPF

Por enquanto, a conferência dos dígitos verificadores do CPF está **desativada**, para permitir testes com CPFs fictícios (o sistema só exige 11 números e não aceita CPF repetido).
Para ativá-la de novo, altere em `services/pacientes.py`:

```python
VALIDAR_CPF = True
```

Os dados de teste devem ser sempre fictícios.