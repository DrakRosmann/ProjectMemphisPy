from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from deloream import DeloreamWindow, read_all_messages, read_task_messages


def _item(window, text):
    return window.tree.findItems(text, Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive)[0]


def _click(window, item):
    rect = window.tree.visualItemRect(item)
    QTest.mouseClick(window.tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())


def test_read_messages(scenario_dir):
    messages = read_all_messages(scenario_dir / "log")
    assert sum(len(task_messages) for task_messages in messages.values()) == 409
    assert read_task_messages(scenario_dir / "log", 3, 0) == messages[(3, 0)]


def test_single_click_opens_tab(qapp, scenario_dir):
    window = DeloreamWindow(str(scenario_dir))
    window.show()
    assert window.tabs.count() == 0

    cons = _item(window, "cons[768]")
    _click(window, cons)
    assert window.tabs.count() == 1
    tab = window.tabs.currentWidget()
    assert tab.kind == "task" and tab.item_id == 768
    assert tab.model.rowCount() == len(window.messages[(3, 0)]) > 0

    # Clicar de novo volta para a mesma aba
    _click(window, cons)
    assert window.tabs.count() == 1

    # Aplicação: mensagens de todas as tarefas, com a coluna da tarefa
    _click(window, _item(window, "prod_cons_custom[3]"))
    assert window.tabs.count() == 2
    app_tab = window.tabs.currentWidget()
    assert app_tab.model.rowCount() == len(window.messages[(3, 0)]) + len(window.messages.get((3, 1), []))
    assert not app_tab.table.isColumnHidden(2)

    app_tab.search.setText("Inicio")
    assert 0 < app_tab.proxy.rowCount() < app_tab.model.rowCount()

    window.close_all_tabs()
    assert window.tabs.count() == 0
    window.close()
