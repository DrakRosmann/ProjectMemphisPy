"""
Mostrar na malha da janela principal o caminho de um pacote analisado.

As janelas de análise (Traffic Statistics, gráfico de escalonamento...)
chamam show_message()/show_record(); a janela principal registra com
set_handler() a função que pinta as setas. Assim as janelas não precisam
conhecer a janela principal.
"""

_handler = None


def set_handler(handler):
    """handler(hops, target, highlight, description); hops = [(roteador, porta de entrada), ...]."""
    global _handler
    _handler = handler


def show_message(message, highlight=None, description=""):
    """Caminho registrado de uma analysis.Message, destacando `highlight` (padrão: onde o pacote está)."""
    if _handler is None:
        return False
    hops = [(router, port) for router, port, _time in message.path]
    if highlight is None:
        highlight = message.last_router
    _handler(hops, message.target, highlight, description)
    return True


def show_record(router, port, target, description=""):
    """Um único registro do trace (quando o pacote não foi identificado)."""
    if _handler is None:
        return False
    _handler([(router, port)], target, router, description)
    return True
