"""Funções de apoio para ler dados e mostrar títulos no terminal."""


def titulo(texto):
    """Mostra um título entre linhas."""
    print()
    print("=" * 56)
    print(texto.center(56))
    print("=" * 56)


def ler_texto(rotulo, padrao=""):
    """Lê um texto. Se o usuário só apertar Enter, mantém o valor padrão.

    Digitar '-' limpa o campo (útil para campos opcionais).
    """
    sufixo = f" [{padrao}]" if padrao else ""
    resposta = input(f"{rotulo}{sufixo}: ").strip()
    if resposta == "-":
        return ""
    return resposta or padrao


def ler_inteiro(rotulo):
    """Lê um número inteiro. Devolve None se a entrada não for um número."""
    texto = input(f"{rotulo}: ").strip()
    if texto.isdigit():
        return int(texto)
    print("Digite apenas números.")
    return None


def confirmar(pergunta):
    """Pergunta sim ou não e devolve True ou False."""
    while True:
        resposta = input(f"{pergunta} (s/n): ").strip().lower()
        if resposta in ("s", "sim"):
            return True
        if resposta in ("n", "nao", "não"):
            return False
        print("Digite 's' para sim ou 'n' para não.")


def pausar():
    input("\nPressione Enter para continuar...")
