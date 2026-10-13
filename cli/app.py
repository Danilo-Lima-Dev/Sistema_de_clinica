"""Menu principal do Sistema de Clínica no terminal."""
from cli.entrada import pausar, titulo
from cli.menu_pacientes import menu_pacientes


def em_desenvolvimento(nome):
    print(f"\n{nome}: ainda em desenvolvimento (previsto para as próximas etapas).")
    pausar()


def executar():
    """Mostra o menu principal até o usuário escolher sair."""
    try:
        while True:
            titulo("SISTEMA DE CLÍNICA")
            print("  1 - Pacientes")
            print("  2 - Profissionais (em desenvolvimento)")
            print("  3 - Consultas (em desenvolvimento)")
            print("  0 - Sair")
            escolha = input("\nEscolha uma opção: ").strip()
            if escolha == "1":
                menu_pacientes()
            elif escolha == "2":
                em_desenvolvimento("Profissionais")
            elif escolha == "3":
                em_desenvolvimento("Consultas")
            elif escolha == "0":
                break
            else:
                print("\nOpção inválida. Digite um dos números do menu.")
    except (KeyboardInterrupt, EOFError):
        print()  # Ctrl+C ou fim da entrada: sai sem mostrar erro
    print("\nSistema encerrado. Até logo!")
