# Sistema de Clínica

Trabalho prático de Desenvolvimento Rápido de Aplicações em Python.
Aplicação desktop (Tkinter) com banco de dados SQLite.

## Estado atual (primeira versão)

| Tela | Situação |
| --- | --- |
| Pacientes | Funcionando: cadastrar, listar, buscar, alterar e excluir |
| Profissionais | Protótipo (layout, sem ligação com o banco) |
| Consultas | Protótipo (layout, sem ligação com o banco) |

O banco já é criado com as 4 tabelas do modelo (`especialidade`, `paciente`, `profissional`, `consulta`).

## Requisitos

- Python 3.9 ou superior
- Tkinter (já vem com o Python no Windows e no macOS)
  - Linux (Debian/Ubuntu): `sudo apt install python3-tk`
- Nenhuma biblioteca externa: não é preciso rodar `pip install`.

## Como executar

```bash
python main.py
```

Na primeira execução o arquivo `clinica.db` é criado automaticamente na pasta do projeto.
Para começar do zero, feche o programa e apague o arquivo `clinica.db`.

## Como testar

```bash
python -m unittest discover -s tests -v
```

## Estrutura

```
main.py                 ponto de entrada
database.py             conexão e criação das tabelas
services/validacoes.py  validação de CPF, datas, telefone e e-mail
services/pacientes.py   regras de negócio e SQL dos pacientes
ui/app.py               janela principal (abas)
ui/tela_pacientes.py    tela de pacientes (funcional)
ui/telas_prototipo.py   telas de protótipo (profissionais e consultas)
tests/test_clinica.py   testes automáticos
```

## Regras já aplicadas

- Nome, CPF e data de nascimento obrigatórios (RN01).
- CPF digitado só com números (11 dígitos), válido e único (RN02).
- Data de nascimento no formato DD/MM/AAAA e não pode ser futura (RN03).
- Paciente com consultas vinculadas não pode ser excluído (RN12).

Os dados de teste devem ser sempre fictícios.
