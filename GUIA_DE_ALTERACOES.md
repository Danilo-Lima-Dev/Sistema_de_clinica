# Sistema de Clínica — alterações (sobre a versão atual do GitHub, com os papéis já existentes)

> Esta entrega **substitui** o zip anterior. Ela foi refeita em cima do commit `7eb598d`
> (PR "permissoes"). **Nada foi enviado ao GitHub.**

## O que já existia no repositório (não precisei refazer)
| Pedido | Situação |
|---|---|
| Recepcionista não gera atestado | Já ok: só o **Médico** emite (atestado e receituário). |
| Perfil de médico | Já ok: papel **Médico** ligado a um profissional. |
| Recepcionista só reimprime | Já ok: o **Atendente** só lê e entrega a 2ª via, com registro de entrega. |

## O que eu acrescentei
1. **Validação na alteração dos dados** (pacientes, profissionais, especialidades, usuários, consultas)
   - Nome: 2+ letras, só letras/espaço/`'`/`.`/`-`, até 100. Registro profissional: 4–30 caracteres, com número.
   - Login: 3–30 (letras, números, `.`, `-`, `_`). Senha: 6–128, diferente do login, sem espaço nas pontas.
   - Observações da consulta: até 500. Consulta paga/confirmada não troca de paciente nem de médico.
   - Ao salvar, a tela avisa **"Nenhuma alteração para salvar"** e **pede confirmação** quando houve mudança.
   - Paciente com histórico/documentos e profissional ligado a usuário não podem ser excluídos.
2. **Histórico clínico por paciente** (menu novo *Histórico clínico*, só para o Médico)
   - Só médico lê e escreve (conferido no back-end); Administrador e Atendente são barrados.
   - Só o médico autor altera a anotação; a versão anterior fica guardada ("Versões anteriores"). Nada é apagado.
3. **Tela Usuários**: agora escolhe o **Perfil** (Administrador/Atendente/Médico) e o **profissional** do médico
   (antes não dava para criar médico pela tela).
4. **Correção de um erro do repositório**: salvar uma especialidade pela tela quebrava
   (`executor_id` passado duas vezes). Corrigido em `services/acesso.py` e `ui/tela_especialidades.py`.
5. **Dados fictícios** (`popular_dados_teste.py`) e README atualizado.

## Onde colocar
Substitua a pasta do projeto pelo conteúdo do zip (ou aplique `alteracoes.patch` com `git apply`).
Bancos existentes ganham as tabelas novas sozinhos na próxima execução (testado numa cópia do seu `clinica.db`).

Arquivos novos: `services/historico_clinico.py`, `ui/tela_historico.py`, `tests/test_validacao_e_historico.py`, `popular_dados_teste.py`.
Alterados: `database.py`, `services/{acesso,autenticacao,consultas,especialidades,menu,pacientes,profissionais,validacoes}.py`,
`ui/{app,dialogos,tela_especialidades,tela_pacientes,tela_profissionais,tela_usuarios}.py`, `README.md` e 4 testes antigos
(ajustados porque nomes/logins de 1–2 letras agora são inválidos).

## Dados de teste e logins
Para usar: apague o `clinica.db` e rode `python popular_dados_teste.py` — ou use o `clinica_com_dados_de_teste.db` pronto (renomeie para `clinica.db`).

| Login | Senha | Papel |
|---|---|---|
| `super` | `super123` | Administrador |
| `admin` | `admin123` | Atendente (usuário padrão do sistema) |
| `recepcao` | `recepcao123` | Atendente |
| `helena` | `medico123` | Médico (Pediatria) |
| `rafael` | `medico123` | Médico (Cardiologia) |
| `luiza` | `medico123` | Médico (Dermatologia) |

Dados: 12 pacientes, 5 profissionais, 15 consultas (realizadas, canceladas, pagas, confirmadas), 3 documentos, 1 entrega de 2ª via e 4 anotações de histórico.
Troque as senhas antes de usar com dados reais.

## Conferido
173 testes passando (151 do repositório + 22 novos), pyflakes sem avisos nas pastas do sistema, e as telas de cada papel abertas e exercitadas em ambiente gráfico simulado.
