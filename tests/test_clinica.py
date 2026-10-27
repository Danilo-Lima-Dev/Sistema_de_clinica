"""Testes automáticos. Execute com:  python -m unittest discover -s tests -v"""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
from services import autenticacao, comprovante, consultas, pacientes, profissionais  # noqa: E402
from services.validacoes import (  # noqa: E402
    ErroValidacao,
    calcular_hora_fim,
    cpf_valido,
    data_br_para_date,
    formatar_cpf,
    hora_valida,
    mascara_data,
    mascara_hora,
)


CPF_OK = "52998224725"  # CPF de teste com dígitos verificadores corretos
CPF_OK_2 = "11144477735"


class TestValidacoes(unittest.TestCase):
    def test_cpf(self):
        self.assertTrue(cpf_valido(CPF_OK))
        self.assertTrue(cpf_valido("529.982.247-25"))  # aceita pontuação
        self.assertFalse(cpf_valido("52998224726"))  # dígito errado
        self.assertFalse(cpf_valido("11111111111"))  # todos iguais
        self.assertFalse(cpf_valido("123"))  # curto

    def test_formatar_cpf(self):
        self.assertEqual(formatar_cpf(CPF_OK), "529.982.247-25")

    def test_data_br(self):
        self.assertEqual(data_br_para_date("25/03/1990").isoformat(), "1990-03-25")
        for invalida in ("1990-03-25", "31/02/2000", "5/3/1990", "", "ab/cd/efgh"):
            with self.assertRaises(ErroValidacao):
                data_br_para_date(invalida)

    def test_mascara_data(self):
        self.assertEqual(mascara_data("25031990"), "25/03/1990")
        self.assertEqual(mascara_data("2503"), "25/03")
        self.assertEqual(mascara_data("25"), "25")
        self.assertEqual(mascara_data("25/03/19901234"), "25/03/1990")


class TestPacientes(unittest.TestCase):
    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._pasta.name) / "teste.db"
        database.criar_tabelas()

    def tearDown(self):
        self._pasta.cleanup()

    def test_cadastrar_e_listar(self):
        id_novo = pacientes.cadastrar("Maria Silva", CPF_OK, "25/03/1990", "11982341234", "m@x.com")
        lista = pacientes.listar()
        self.assertEqual(len(lista), 1)
        self.assertEqual(lista[0]["id"], id_novo)
        self.assertEqual(lista[0]["data_nascimento"], "1990-03-25")  # ISO no banco
        self.assertEqual(lista[0]["cpf"], CPF_OK)  # só números no banco

    def test_cpf_aceita_pontuacao_mas_grava_so_numeros(self):
        pacientes.cadastrar("Ana", "529.982.247-25", "01/01/2000")
        self.assertEqual(pacientes.listar()[0]["cpf"], CPF_OK)

    def test_obrigatorios(self):
        casos = [
            ("", CPF_OK, "25/03/1990"),
            ("Ana", "", "25/03/1990"),
            ("Ana", CPF_OK, ""),
        ]
        for nome, cpf, nasc in casos:
            with self.assertRaises(ErroValidacao):
                pacientes.cadastrar(nome, cpf, nasc)

    def test_cpf_com_menos_de_11_numeros_e_sempre_recusado(self):
        with self.assertRaises(ErroValidacao):
            pacientes.cadastrar("Ana", "123456789", "25/03/1990")

    def test_cpf_falso_modo_teste_e_modo_estrito(self):
        pacientes.VALIDAR_CPF = False  # modo de teste: aceita CPF falso
        pacientes.cadastrar("Ana", "12345678900", "25/03/1990")
        pacientes.VALIDAR_CPF = True  # modo estrito: confere os dígitos
        try:
            with self.assertRaises(ErroValidacao):
                pacientes.cadastrar("Beto", "11111111111", "25/03/1990")
        finally:
            pacientes.VALIDAR_CPF = False

    def test_cpf_duplicado(self):
        pacientes.cadastrar("Ana", CPF_OK, "25/03/1990")
        with self.assertRaises(ErroValidacao):
            pacientes.cadastrar("Outra Ana", CPF_OK, "01/01/1980")

    def test_data_futura_e_telefone_e_email(self):
        with self.assertRaises(ErroValidacao):
            pacientes.cadastrar("Ana", CPF_OK, "01/01/2999")
        with self.assertRaises(ErroValidacao):
            pacientes.cadastrar("Ana", CPF_OK, "01/01/2000", telefone="123")
        with self.assertRaises(ErroValidacao):
            pacientes.cadastrar("Ana", CPF_OK, "01/01/2000", email="sem-arroba")

    def test_atualizar(self):
        id_p = pacientes.cadastrar("Ana", CPF_OK, "25/03/1990")
        pacientes.atualizar(id_p, "Ana Souza", CPF_OK, "25/03/1990")
        self.assertEqual(pacientes.listar()[0]["nome"], "Ana Souza")

    def test_atualizar_cpf_de_outro_paciente(self):
        pacientes.cadastrar("Ana", CPF_OK, "25/03/1990")
        id_b = pacientes.cadastrar("Beto", CPF_OK_2, "01/01/1985")
        with self.assertRaises(ErroValidacao):
            pacientes.atualizar(id_b, "Beto", CPF_OK, "01/01/1985")

    def test_buscar_por_nome_e_cpf(self):
        pacientes.cadastrar("Maria Silva", CPF_OK, "25/03/1990")
        pacientes.cadastrar("João Souza", CPF_OK_2, "01/01/1985")
        self.assertEqual([p["nome"] for p in pacientes.listar("maria")], ["Maria Silva"])
        self.assertEqual([p["nome"] for p in pacientes.listar("111.444")], ["João Souza"])
        self.assertEqual(pacientes.listar("inexistente"), [])

    def test_excluir_e_bloqueio_com_consulta(self):
        livre = pacientes.cadastrar("Livre", CPF_OK, "25/03/1990")
        pacientes.excluir(livre)
        self.assertEqual(pacientes.listar(), [])

        com_consulta = pacientes.cadastrar("Com Consulta", CPF_OK_2, "01/01/1985")
        with database.transacao() as con:
            con.execute(
                "INSERT INTO profissional (nome, registro, especialidade_id) VALUES ('Dr. X', 'CRM1', 1)"
            )
            con.execute(
                "INSERT INTO consulta (paciente_id, profissional_id, data, hora_inicio, hora_fim) "
                "VALUES (?, 1, '2030-01-01', '09:00', '09:30')",
                (com_consulta,),
            )
        with self.assertRaises(ErroValidacao):  # RN04
            pacientes.excluir(com_consulta)
        self.assertEqual(len(pacientes.listar()), 1)


class TestAutenticacao(unittest.TestCase):
    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._pasta.name) / "login.db"
        database.criar_tabelas()

    def tearDown(self):
        self._pasta.cleanup()

    def test_usuario_padrao_criado_uma_vez(self):
        autenticacao.criar_usuario_padrao()
        autenticacao.criar_usuario_padrao()  # não duplica
        with database.transacao() as con:
            total = con.execute("SELECT COUNT(*) FROM usuario").fetchone()[0]
        self.assertEqual(total, 1)

    def test_login_correto(self):
        autenticacao.criar_usuario_padrao()
        usuario = autenticacao.autenticar("ADMIN", autenticacao.SENHA_PADRAO)  # ignora maiúsculas
        self.assertEqual(usuario["login"], "admin")

    def test_login_errado(self):
        autenticacao.criar_usuario_padrao()
        for login, senha in (("admin", "errada"), ("naoexiste", "admin123"), ("", ""), ("admin", "")):
            with self.assertRaises(ErroValidacao):
                autenticacao.autenticar(login, senha)

    def test_senha_nao_fica_em_texto_puro(self):
        autenticacao.cadastrar_usuario("Ana", "ana", "segredo123")
        with database.transacao() as con:
            guardado = con.execute("SELECT senha_hash FROM usuario").fetchone()[0]
        self.assertNotIn("segredo123", guardado)

    def test_cadastro_invalido(self):
        autenticacao.cadastrar_usuario("Ana", "ana", "segredo123")
        with self.assertRaises(ErroValidacao):
            autenticacao.cadastrar_usuario("Outra", "ANA", "segredo123")  # login repetido
        with self.assertRaises(ErroValidacao):
            autenticacao.cadastrar_usuario("Bia", "bia", "123")  # senha curta


class TestSuperUsuario(unittest.TestCase):
    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._pasta.name) / "super.db"
        database.criar_tabelas()
        autenticacao.criar_usuario_padrao()
        autenticacao.criar_superusuario_padrao()
        self.super = autenticacao.autenticar(autenticacao.SUPER_LOGIN, autenticacao.SUPER_SENHA)
        self.comum = autenticacao.autenticar("admin", autenticacao.SENHA_PADRAO)

    def tearDown(self):
        self._pasta.cleanup()

    def test_superusuario_criado_uma_vez_e_com_perfil(self):
        autenticacao.criar_superusuario_padrao()  # não duplica
        self.assertTrue(self.super["superusuario"])
        self.assertFalse(self.comum["superusuario"])  # o admin continua comum
        ids = [u["id"] for u in autenticacao.listar_usuarios(self.super["id"])]
        self.assertEqual(len(ids), 2)

    def test_usuario_comum_nao_gerencia(self):
        with self.assertRaises(ErroValidacao):
            autenticacao.listar_usuarios(self.comum["id"])
        with self.assertRaises(ErroValidacao):
            autenticacao.cadastrar_usuario_por(self.comum["id"], "Ana", "ana", "segredo123")
        with self.assertRaises(ErroValidacao):
            autenticacao.atualizar_usuario(self.comum["id"], self.comum["id"], "X", "admin", superusuario=True)

    def test_superusuario_cadastra_e_novo_usuario_entra(self):
        autenticacao.cadastrar_usuario_por(self.super["id"], "Ana", "Ana", "segredo123")
        self.assertFalse(autenticacao.autenticar("ana", "segredo123")["superusuario"])

    def test_superusuario_troca_dados_e_senha(self):
        autenticacao.atualizar_usuario(
            self.super["id"], self.comum["id"], "Admin Novo", "admin2", senha="novasenha1"
        )
        usuario = autenticacao.autenticar("admin2", "novasenha1")
        self.assertEqual(usuario["nome"], "Admin Novo")
        with self.assertRaises(ErroValidacao):
            autenticacao.autenticar("admin", autenticacao.SENHA_PADRAO)

    def test_senha_em_branco_mantem_a_atual(self):
        autenticacao.atualizar_usuario(self.super["id"], self.comum["id"], "Admin", "admin", senha="")
        autenticacao.autenticar("admin", autenticacao.SENHA_PADRAO)

    def test_troca_com_dados_invalidos(self):
        with self.assertRaises(ErroValidacao):  # senha curta
            autenticacao.atualizar_usuario(self.super["id"], self.comum["id"], "A", "admin", senha="123")
        with self.assertRaises(ErroValidacao):  # login já usado
            autenticacao.atualizar_usuario(self.super["id"], self.comum["id"], "A", "super")
        with self.assertRaises(ErroValidacao):  # usuário inexistente
            autenticacao.atualizar_usuario(self.super["id"], 999, "A", "zzz")

    def test_nao_remove_o_ultimo_superusuario(self):
        with self.assertRaises(ErroValidacao):  # se desativar
            autenticacao.atualizar_usuario(self.super["id"], self.super["id"], "S", "super", ativo=False, superusuario=True)
        with self.assertRaises(ErroValidacao):  # se deixar de ser super
            autenticacao.atualizar_usuario(self.super["id"], self.super["id"], "S", "super", ativo=True, superusuario=False)
        # com outro super ativo, já pode
        autenticacao.atualizar_usuario(self.super["id"], self.comum["id"], "Admin", "admin", superusuario=True)
        autenticacao.atualizar_usuario(self.comum["id"], self.super["id"], "S", "super", superusuario=False)

    def test_usuario_desativado_nao_entra(self):
        autenticacao.atualizar_usuario(self.super["id"], self.comum["id"], "Admin", "admin", ativo=False)
        with self.assertRaises(ErroValidacao):
            autenticacao.autenticar("admin", autenticacao.SENHA_PADRAO)

    def test_excluir_usuario(self):
        autenticacao.excluir_usuario(self.super["id"], self.comum["id"])
        with self.assertRaises(ErroValidacao):
            autenticacao.autenticar("admin", autenticacao.SENHA_PADRAO)
        self.assertEqual(len(autenticacao.listar_usuarios(self.super["id"])), 1)

    def test_excluir_com_regras(self):
        with self.assertRaises(ErroValidacao):  # usuário comum não exclui
            autenticacao.excluir_usuario(self.comum["id"], self.super["id"])
        with self.assertRaises(ErroValidacao):  # não exclui a si mesmo
            autenticacao.excluir_usuario(self.super["id"], self.super["id"])
        with self.assertRaises(ErroValidacao):  # inexistente
            autenticacao.excluir_usuario(self.super["id"], 999)
        self.assertEqual(len(autenticacao.listar_usuarios(self.super["id"])), 2)

    def test_banco_antigo_ganha_a_coluna(self):
        with database.transacao() as con:
            con.executescript("DROP TABLE usuario; CREATE TABLE usuario (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                              "nome TEXT NOT NULL, login TEXT NOT NULL UNIQUE, senha_hash TEXT NOT NULL, "
                              "ativo INTEGER NOT NULL DEFAULT 1);")
        database.criar_tabelas()  # migra
        autenticacao.criar_superusuario_padrao()
        self.assertTrue(autenticacao.autenticar("super", autenticacao.SUPER_SENHA)["superusuario"])


class TestBanco(unittest.TestCase):
    def test_persistencia_apos_reabrir(self):
        with tempfile.TemporaryDirectory() as pasta:
            database.DB_PATH = Path(pasta) / "persist.db"
            database.criar_tabelas()
            pacientes.cadastrar("Ana", CPF_OK, "25/03/1990")
            database.criar_tabelas()  # simula fechar e abrir o sistema
            self.assertEqual(len(pacientes.listar()), 1)
            with database.transacao() as con:
                total = con.execute("SELECT COUNT(*) FROM especialidade").fetchone()[0]
            self.assertEqual(total, len(database.ESPECIALIDADES_INICIAIS))  # sem duplicar

    def test_persistencia_de_todas_as_entidades(self):
        """Etapa 3: o que foi cadastrado continua lá depois de fechar e abrir de novo."""
        with tempfile.TemporaryDirectory() as pasta:
            database.DB_PATH = Path(pasta) / "persist_todas.db"
            database.criar_tabelas()
            id_pac = pacientes.cadastrar("Ana", CPF_OK, "25/03/1990")
            id_prof = profissionais.cadastrar("Dr. Caio", "CRM 777", "Pediatria")
            consultas.agendar(id_pac, id_prof, "20/12/2030", "09:00")

            database.criar_tabelas()  # simula fechar e abrir o sistema
            self.assertEqual(len(pacientes.listar()), 1)
            self.assertEqual(len(profissionais.listar()), 1)
            lista = consultas.listar()
            self.assertEqual(len(lista), 1)  # o relacionamento paciente x profissional também persiste
            self.assertEqual(lista[0]["paciente_nome"], "Ana")
            self.assertEqual(lista[0]["profissional_nome"], "Dr. Caio")


class TestProfissionais(unittest.TestCase):
    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._pasta.name) / "teste_prof.db"
        database.criar_tabelas()

    def tearDown(self):
        self._pasta.cleanup()

    def test_cadastrar_e_listar(self):
        id_m = profissionais.cadastrar("Dr. Roberto Carlos", "CRM/SP 123456", "Cardiologia", "11982341234")
        lista = profissionais.listar()
        self.assertEqual(len(lista), 1)
        self.assertEqual(lista[0]["id"], id_m)
        self.assertEqual(lista[0]["nome"], "Dr. Roberto Carlos")
        self.assertEqual(lista[0]["registro"], "CRM/SP 123456")
        self.assertEqual(lista[0]["especialidade"], "Cardiologia")
        self.assertEqual(lista[0]["ativo"], 1)

    def test_obrigatorios(self):
        with self.assertRaises(ErroValidacao):
            profissionais.cadastrar("", "CRM 123", "Cardiologia")
        with self.assertRaises(ErroValidacao):
            profissionais.cadastrar("Dr. Roberto", "", "Cardiologia")
        with self.assertRaises(ErroValidacao):
            profissionais.cadastrar("Dr. Roberto", "CRM 123", "")

    def test_registro_duplicado(self):
        profissionais.cadastrar("Dr. Um", "CRM 999", "Pediatria")
        with self.assertRaises(ErroValidacao):  # RN06
            profissionais.cadastrar("Dr. Dois", "CRM 999", "Cardiologia")

    def test_buscar_por_nome_e_especialidade(self):
        profissionais.cadastrar("Dra. Paula", "CRM 111", "Pediatria")
        profissionais.cadastrar("Dr. Lucas", "CRM 222", "Dermatologia")
        # RF04
        self.assertEqual([p["nome"] for p in profissionais.listar("paula")], ["Dra. Paula"])
        self.assertEqual([p["nome"] for p in profissionais.listar("dermato")], ["Dr. Lucas"])
        self.assertEqual(profissionais.listar("inexistente"), [])

    def test_atualizar(self):
        id_m = profissionais.cadastrar("Dr. Carlos", "CRM 333", "Ortopedia")
        profissionais.atualizar(id_m, "Dr. Carlos Silva", "CRM 333", "Ortopedia", "11999998888")
        obter = profissionais.obter(id_m)
        self.assertEqual(obter["nome"], "Dr. Carlos Silva")
        self.assertEqual(obter["telefone"], "11999998888")

    def test_alternar_ativo(self):
        id_m = profissionais.cadastrar("Dr. Ativo", "CRM 444", "Clínica Geral")
        novo = profissionais.alternar_ativo(id_m)
        self.assertEqual(novo, 0)
        self.assertEqual(profissionais.obter(id_m)["ativo"], 0)
        novo = profissionais.alternar_ativo(id_m)
        self.assertEqual(novo, 1)

    def test_excluir_e_bloqueio_com_consulta(self):
        id_m = profissionais.cadastrar("Dr. Sem Consulta", "CRM 555", "Pediatria")
        profissionais.excluir(id_m)
        self.assertEqual(profissionais.listar(), [])

        id_com = profissionais.cadastrar("Dr. Com Consulta", "CRM 666", "Cardiologia")
        id_pac = pacientes.cadastrar("Paciente Teste", CPF_OK, "01/01/1990")
        consultas.agendar(id_pac, id_com, "16/12/2030", "14:00")
        with self.assertRaises(ErroValidacao):  # RN04
            profissionais.excluir(id_com)
        self.assertEqual(len(profissionais.listar()), 1)


class TestConsultas(unittest.TestCase):
    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._pasta.name) / "teste_cons.db"
        database.criar_tabelas()
        self.id_paciente = pacientes.cadastrar("Paciente Teste", CPF_OK, "01/01/1990")
        self.id_prof = profissionais.cadastrar("Dra. Beatriz", "CRM 123", "Cardiologia")

    def tearDown(self):
        self._pasta.cleanup()

    def test_agendar_e_listar(self):
        id_c = consultas.agendar(
            self.id_paciente, self.id_prof, "20/12/2030", "10:00", observacoes="Primeira consulta"
        )
        lista = consultas.listar()
        self.assertEqual(len(lista), 1)
        self.assertEqual(lista[0]["id"], id_c)
        self.assertEqual(lista[0]["paciente_nome"], "Paciente Teste")
        self.assertEqual(lista[0]["profissional_nome"], "Dra. Beatriz")
        self.assertEqual(lista[0]["hora_inicio"], "10:00")
        self.assertEqual(lista[0]["hora_fim"], "10:30")
        self.assertEqual(lista[0]["situacao"], "Agendada")

    def test_conflito_horario_mesmo_profissional(self):
        consultas.agendar(self.id_paciente, self.id_prof, "20/12/2030", "10:00")
        id_outro = pacientes.cadastrar("Outro Paciente", CPF_OK_2, "02/02/1995")
        with self.assertRaises(ErroValidacao):  # RN01
            consultas.agendar(id_outro, self.id_prof, "20/12/2030", "10:00")

    def test_conflito_por_sobreposicao_de_horario(self):
        """RN01: consulta dura 30 min, então horários que se sobrepõem devem ser recusados."""
        consultas.agendar(self.id_paciente, self.id_prof, "20/12/2030", "09:00")  # 09:00-09:30
        id_outro = pacientes.cadastrar("Outro Paciente", CPF_OK_2, "02/02/1995")

        # começa dentro da consulta existente
        with self.assertRaises(ErroValidacao):
            consultas.agendar(id_outro, self.id_prof, "20/12/2030", "09:15")
        with self.assertRaises(ErroValidacao):
            consultas.agendar(id_outro, self.id_prof, "20/12/2030", "09:29")
        # termina depois que a existente já começou
        with self.assertRaises(ErroValidacao):
            consultas.agendar(id_outro, self.id_prof, "20/12/2030", "08:45")

        # horários colados, sem sobreposição, são permitidos
        consultas.agendar(id_outro, self.id_prof, "20/12/2030", "09:30")
        consultas.agendar(id_outro, self.id_prof, "20/12/2030", "08:30")

    def test_consulta_cancelada_libera_horario(self):
        id_c = consultas.agendar(self.id_paciente, self.id_prof, "20/12/2030", "10:00")
        consultas.cancelar(id_c, "Paciente solicitou cancelamento")
        id_outro = pacientes.cadastrar("Outro Paciente", CPF_OK_2, "02/02/1995")
        # RN01: Consultas com situação 'Cancelada' não bloqueiam o horário
        id_novo = consultas.agendar(id_outro, self.id_prof, "20/12/2030", "10:00")
        self.assertIsNotNone(id_novo)

    def test_data_passada_bloqueada(self):
        with self.assertRaises(ErroValidacao):  # RN05
            consultas.agendar(self.id_paciente, self.id_prof, "01/01/2020", "10:00")

    def test_remarcar_alterar(self):
        id_c = consultas.agendar(self.id_paciente, self.id_prof, "20/12/2030", "10:00")
        consultas.alterar_dados(id_c, self.id_paciente, self.id_prof, "23/12/2030", "15:00", "Remarcado")
        obtida = consultas.obter(id_c)
        self.assertEqual(obtida["data"], "2030-12-23")
        self.assertEqual(obtida["hora_inicio"], "15:00")
        self.assertEqual(obtida["observacoes"], "Remarcado")

    def test_cancelar_consulta(self):
        id_c = consultas.agendar(self.id_paciente, self.id_prof, "20/12/2030", "10:00")
        consultas.cancelar(id_c, "Imprevisto")
        obtida = consultas.obter(id_c)
        self.assertEqual(obtida["situacao"], "Cancelada")  # RN07
        self.assertEqual(obtida["motivo_cancelamento"], "Imprevisto")

    def test_marcar_realizada(self):
        id_c = consultas.agendar(self.id_paciente, self.id_prof, "20/12/2030", "10:00")
        consultas.marcar_realizada(id_c)
        obtida = consultas.obter(id_c)
        self.assertEqual(obtida["situacao"], "Realizada")  # RF09

    def test_medico_inativo_nao_agenda(self):
        profissionais.alternar_ativo(self.id_prof)
        with self.assertRaises(ErroValidacao):
            consultas.agendar(self.id_paciente, self.id_prof, "20/12/2030", "10:00")

    def test_indice_unico_garante_conflito_no_banco(self):
        """RN01 também no banco: nem um INSERT direto consegue duplicar o horário."""
        consultas.agendar(self.id_paciente, self.id_prof, "20/12/2030", "10:00")
        sql = (
            "INSERT INTO consulta (paciente_id, profissional_id, data, hora_inicio, hora_fim, situacao) "
            "VALUES (?, ?, '2030-12-20', '10:00', '10:30', ?)"
        )
        with self.assertRaises(sqlite3.IntegrityError):
            with database.transacao() as con:
                con.execute(sql, (self.id_paciente, self.id_prof, "Agendada"))
        with database.transacao() as con:  # consulta cancelada não bloqueia
            con.execute(sql, (self.id_paciente, self.id_prof, "Cancelada"))

    def test_banco_antigo_com_conflito_ainda_abre(self):
        """Se um banco antigo já tem horários duplicados, o sistema abre mesmo assim."""
        with database.transacao() as con:
            con.execute("DROP INDEX ux_consulta_profissional_horario")
            for _ in range(2):
                con.execute(
                    "INSERT INTO consulta (paciente_id, profissional_id, data, hora_inicio, hora_fim) "
                    "VALUES (?, ?, '2030-12-20', '10:00', '10:30')",
                    (self.id_paciente, self.id_prof),
                )
        database.criar_tabelas()  # não pode levantar erro
        self.assertEqual(len(consultas.listar()), 2)

    def test_busca_por_data(self):
        """RF06: digitar uma data DD/MM/AAAA na busca encontra as consultas daquele dia."""
        consultas.agendar(self.id_paciente, self.id_prof, "20/12/2030", "10:00")
        consultas.agendar(self.id_paciente, self.id_prof, "23/12/2030", "10:00")
        self.assertEqual(len(consultas.listar(busca="20/12/2030")), 1)
        self.assertEqual(len(consultas.listar(busca="22/12/2030")), 0)
        self.assertEqual(len(consultas.listar(busca="Beatriz")), 2)  # busca por nome continua valendo


class TestComprovante(unittest.TestCase):
    """Comprovante de agendamento para impressora térmica."""

    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._pasta.name) / "comprovante.db"
        database.criar_tabelas()
        pac = pacientes.cadastrar("Maria Silva", CPF_OK, "25/03/1990", "86999990001")
        prof = profissionais.cadastrar("Dra. Helena Duarte", "CRM-PI 2002", "Pediatria", "")
        self.id_consulta = consultas.agendar(pac, prof, "01/01/2099", "09:30", "Retorno")

    def tearDown(self):
        self._pasta.cleanup()

    def test_dados_e_texto_trazem_tudo(self):
        d = comprovante.dados_do_comprovante(self.id_consulta)
        texto = comprovante.gerar_texto(d, 80)
        for esperado in ("Maria Silva", "529.***.***-25", "(86) 99999-0001", "Dra. Helena Duarte",
                         "CRM-PI 2002", "Pediatria", "01/01/2099", "09:30 as 10:00", "Agendada"):
            self.assertIn(esperado, texto)

    def test_cpf_sai_mascarado(self):
        d = comprovante.dados_do_comprovante(self.id_consulta)
        self.assertEqual(d["cpf"], "529.***.***-25")
        self.assertNotIn("982.247", comprovante.gerar_texto(d))
        self.assertNotIn("982", comprovante.gerar_html(d).split("<body")[1])
        self.assertEqual(comprovante.mascarar_cpf("123"), "***.***.***-**")

    def test_texto_respeita_largura_da_bobina(self):
        d = comprovante.dados_do_comprovante(self.id_consulta)
        for mm, colunas in ((80, 42), (58, 32)):
            for linha in comprovante.gerar_texto(d, mm).splitlines():
                self.assertLessEqual(len(linha), colunas)

    def test_html_tem_largura_da_bobina_e_escapa_texto(self):
        d = comprovante.dados_do_comprovante(self.id_consulta)
        d["observacoes"] = "<b>teste</b>"
        pagina = comprovante.gerar_html(d, 58)
        self.assertIn("width: 50mm", pagina)
        self.assertIn("&lt;b&gt;teste&lt;/b&gt;", pagina)

    def test_consulta_inexistente(self):
        with self.assertRaises(ErroValidacao):
            comprovante.dados_do_comprovante(9999)


if __name__ == "__main__":
    unittest.main()