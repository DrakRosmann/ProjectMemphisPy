"""Testes rápidos das janelas (sem tela, com os diálogos substituídos)."""

import os

import pytest
from PySide6.QtWidgets import QDialog

import projects


@pytest.fixture
def window(qapp, dialogs, debug_dir):
    import main
    main_window = main.MinhaJanela()
    assert main_window.load_debug(debug_dir)
    yield main_window
    main_window.close_router_info_windows()
    main_window.stop_simulation()
    main_window.close()
    main_window.deleteLater()


def run_to_end(window):
    while window.simulation.next_packet(repaint=False) != -1:
        pass


def test_load_and_simulate(window):
    assert window.windowTitle().endswith("example_scenario")
    window.simulation.step()
    assert window.simulation_ticks > 0
    run_to_end(window)
    assert window.simulation_ticks == 6251176


def test_invalid_directory(qapp, dialogs, tmp_path):
    import main
    main_window = main.MinhaJanela()
    assert not main_window.load_debug(str(tmp_path))
    assert dialogs.shown and dialogs.shown[0][0] == "critical"


def test_router_info_window(window):
    run_to_end(window)
    window.open_router_info(0)
    router_window = window.router_info_windows[0]
    router_window.refresh()
    assert router_window.traffic_table.item(10, 1).text() == "6864 flits"
    router_window.log_tab.update_log()
    assert "Initializing PE 0" in router_window.log_tab.text.toPlainText()
    router_window._open_task_info(0, 0)
    assert router_window.task_windows[0].status_label.text() == "Running"


def test_application_filter(window):
    import analysis
    filter_window = window.filter_window
    tab = filter_window.app_tab
    tab.combo.setCurrentIndex(tab.combo.findData(2))
    tab.add_selected()
    tab._apply()
    seen = set()
    while (packet := window.mpsoc_information.get_next_packet(window.simulation.packet_filter)) is not None:
        seen |= analysis.packet_apps(packet, filter_window.known_apps)
    assert seen == {2}


def test_traffic_statistics_tabs(window):
    run_to_end(window)
    window.open_traffic_statistics()
    statistics = window.traffic_statistics_window
    for index in range(statistics.tabs.count()):
        statistics.tabs.setCurrentIndex(index)
        statistics.refresh()
    assert statistics.links_table.rowCount() > 0
    assert statistics.apps_table.rowCount() == 4
    assert statistics.violations_table.rowCount() == 0
    assert "No XY routing violation" in statistics.routing_summary.text()
    assert "No packet stopped" in statistics.deadlock_label.text()
    assert statistics.blocked_table.rowCount() == 0


def test_statistics_restart_after_going_back(window):
    run_to_end(window)
    window.open_traffic_statistics()
    statistics = window.traffic_statistics_window
    statistics.refresh()
    total = statistics.tracker.consumed
    window.simulation.go_to_time(300000)
    statistics.refresh()
    assert 0 < statistics.tracker.consumed < total


def test_application_timeline(window):
    window.open_application_timeline()
    timeline = window.timeline_window
    assert timeline.table.rowCount() == 4
    timeline.zoom_combo.setCurrentIndex(1)
    start, end = timeline.chart.range
    assert end < 1_000_000


def test_exports(window, tmp_path, monkeypatch):
    import export
    from PySide6.QtWidgets import QFileDialog
    run_to_end(window)
    window.open_traffic_statistics()
    statistics = window.traffic_statistics_window
    statistics.tabs.setCurrentIndex(1)
    statistics.refresh()

    csv_path = tmp_path / "apps.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(csv_path), "")))
    statistics._export_current_table()
    assert csv_path.read_text().startswith("Application,Messages")

    png_path = tmp_path / "mesh"   # extensão é acrescentada
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(png_path), "")))
    window.save_mesh_png()
    assert os.path.getsize(str(png_path) + ".png") > 0


def test_platform_setup(window):
    from platform_setup import PlatformSetupDialog
    dialog = PlatformSetupDialog(window.mpconfig, window.simulation.checkpoint, window)
    dialog.clock_edit.setText("20")
    dialog.window_width_edit.setText("250")
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert window.mpconfig.clock_period_in_ns == 20
    assert window.simulation.checkpoint.window_size_ms == 0.25


def test_save_and_open_project(window, dialogs, debug_dir):
    dialogs.texts += [("has space", True), ("example", True)]
    window.save_project()
    assert ("critical", "Error", "Name contains space") in dialogs.shown
    assert projects.read_project(projects.project_path("example")) == os.path.abspath(debug_dir)

    window._choose_project = lambda *args: projects.project_path("example")
    window.open_project()
    assert window.windowTitle().endswith(": example")

    window.delete_project()
    assert not os.path.exists(projects.project_path("example"))


def test_peripherals_on_mesh(window):
    matrix = window.router_matrix_widget
    assert matrix.get_router(0, 0).peripherals == {"S": "MA_INJ"}
    assert matrix.get_router(2, 2).peripherals == {"N": "APP_INJ"}
    assert matrix.get_router(1, 1).peripherals == {}


def test_show_path_from_statistics(window):
    run_to_end(window)
    window.open_traffic_statistics()
    statistics = window.traffic_statistics_window
    statistics.tabs.setCurrentIndex(2)
    statistics.refresh()
    # Primeira mensagem com mais de um hop
    model = statistics.message_model
    row = next(row for row, message in enumerate(model.messages) if message.hops >= 2)
    message = model.messages[row]
    statistics._show_message_path(statistics.message_filter.mapFromSource(model.index(row, 0)))

    matrix = window.router_matrix_widget
    painted = [address for address, router in matrix.routers_by_address.items() if router.need_reset]
    assert {router for router, _port, _time in message.path} <= set(painted)
    assert matrix.get_router_by_address(message.target).highlighted
    assert not window.simulation.running

    window.reset_graphical_path()
    assert not any(router.need_reset for router in matrix.routers.values())


def test_scheduling_slice_packets(window):
    from router_info_window import SchedulingGraphWindow
    graph_window = SchedulingGraphWindow(window.mpconfig, 0)   # PE 0x0 (mapper)
    graph = graph_window.graph
    interruption = next(event for event in graph.events if event.name == "Interruption")
    graph.selection_changed.emit(interruption)
    assert graph_window.slice_table.rowCount() > 0
    assert graph_window.slice_table.item(0, 1).text() in ("received", "sent")
    graph_window._show_slice_message(0, 0)
    assert any(router.need_reset for router in window.router_matrix_widget.routers.values())
    graph_window.close()


def test_follow_live_trace(qapp, dialogs, debug_dir, tmp_path):
    import shutil

    import main
    debug = tmp_path / "scenario" / "debug"
    shutil.copytree(debug_dir, debug)
    traffic = debug / "traffic_router.txt"
    lines = traffic.read_text().splitlines(keepends=True)
    traffic.write_text("".join(lines[:100]))

    main_window = main.MinhaJanela()
    assert main_window.load_debug(str(debug))
    main_window.actionFollow_Live_Trace.setChecked(True)
    simulation = main_window.simulation
    simulation.play()
    while simulation.next_packet(repaint=False) != -1:
        pass
    assert simulation.running and simulation.waiting        # fim do arquivo: continua esperando
    assert len(main_window.mpsoc_information.read_traffic.all_packets) == 100

    with open(traffic, "a") as traffic_file:
        traffic_file.write("".join(lines[100:150]))
    while simulation.next_packet(repaint=False) != -1:
        pass
    assert len(main_window.mpsoc_information.read_traffic.all_packets) == 150

    main_window.actionFollow_Live_Trace.setChecked(False)
    assert simulation.next_packet(repaint=False) == -1
    assert not simulation.running                          # sem follow, o fim do arquivo para a simulação
    main_window.close()
