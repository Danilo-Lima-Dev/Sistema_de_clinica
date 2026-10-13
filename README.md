# Sistema de Clínica

Trabalho prático de Desenvolvimento Rápido de Aplicações em Python.
Aplicação de **terminal** (menu em texto) com banco de dados SQLite.

## Estado atual (primeira versão)

| Módulo | Situação |
| --- | --- |
| Pacientes | Funcionando: cadastrar, listar, buscar, alterar e excluir |
| Profissionais | Em desenvolvimento |
| Consultas | Em desenvolvimento |

O banco já é criado com as 4 tabelas do modelo (`especialidade`, `paciente`, `profissional`, `consulta`).

## Requisitos

- Python 3.9 ou superior
- Nenhuma biblioteca externa: não é preciso rodar `pip install`.

## Como executar

```bash
python main.py
```

Na primeira execução o arquivo `clinica.db` é criado automaticamente na pasta do projeto.
Para começar do zero, feche o programa e apague o arquivo `clinica.db`.

## Como usar

O programa mostra um menu numerado. Digite o número da opção e aperte Enter.

```
SISTEMA DE CLÍNICA
  1 - Pacientes        →  1 Cadastrar  2 Listar  3 Buscar  4 Alterar  5 Excluir
  2 - Profissionais (em desenvolvimento)
  3 - Consultas (em desenvolvimento)
  0 - Sair
```

- **CPF e telefone:** digite só os números, sem pontos, traço ou parênteses.
- **Data:** digite `25/03/1990` ou `25031990`.
- **Alterar:** aperte Enter para manter o valor que aparece entre colchetes; digite `-` para limpar um campo opcional.
- **Erro de digitação:** o sistema explica o problema e deixa corrigir sem digitar tudo de novo.

## Como testar

```bash
python -m unittest discover -s tests -v
```

## Estrutura do projeto

| Arquivo | Função |
| --- | --- |
| `main.py` | Ponto de entrada: cria o banco (se não existir) e abre o menu. |
| `database.py` | Conexão com o SQLite e criação das 4 tabelas. |
| `clinica.db` | Banco de dados, criado automaticamente na primeira execução. |
| `cli/app.py` | Menu principal. |
| `cli/menu_pacientes.py` | Menu de pacientes: perguntas, tabela e mensagens. |
| `cli/entrada.py` | Funções de apoio para ler dados e mostrar títulos. |
| `services/validacoes.py` | Validação e formatação de CPF, datas, telefone e e-mail. |
| `services/pacientes.py` | Regras de negócio e SQL do cadastro de pacientes. |
| `tests/test_clinica.py` | Testes automáticos das validações, das regras e da persistência dos dados. |
| `__init__.py` (em `cli/` e `services/`) | Arquivos vazios que permitem importar as pastas como pacotes. |

## Organização em camadas

```
main.py → cli/ (terminal) → services/ (regras) → database.py → clinica.db
```

- **cli/**: só pergunta e mostra os dados; não escreve SQL.
- **services/**: concentra as validações e as regras de negócio.
- **database.py**: concentra o acesso ao banco.

A interface foi trocada de gráfica (Tkinter) para terminal sem mexer em `services/` nem em `database.py`.
Isso mostra o benefício da separação em camadas: as regras funcionam com qualquer tipo de interface.

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
