"""Leitura do platform.cfg / services.cfg e conversões de endereço."""

import pytest

from util.MPSoCConfig import MPSoCConfig


def test_platform(config):
    assert config.router_addressing == MPSoCConfig.XY
    assert (config.mpsoc_x, config.mpsoc_y) == (3, 3)
    assert config.flit_size == 32
    assert config.clock_period_in_ns == 10
    assert config.get_pe_number() == 9


def test_task_and_app_names(config):
    assert config.task_name_hash[0] == "mapper_task"
    assert config.task_name_hash[256] == "taskA"
    assert dict(config.app_name_hash) == {0: "management", 1: "synthetic_default",
                                          2: "prod_cons_custom", 3: "prod_cons_custom"}


def test_services(config):
    assert config.get_service_value("MESSAGE_REQUEST") == 41
    assert config.get_string_service_name(43) == "MESSAGE_DELIVERY"
    assert config.get_service_value("DOES_NOT_EXIST") == -1
    assert 42 in config.task_allocation_services
    assert 6 in config.task_terminated_services


@pytest.mark.parametrize("address", range(9))
def test_address_round_trip(config, address):
    assert config.xy_to_ham_addr(config.ham_to_xy_addr(address)) == address
    label = config.ham_address_to_xy_label(address)
    assert config.xy_label_to_ham_address(label) == address


def test_hamiltonian_snake(config):
    # Linhas ímpares são percorridas da direita para a esquerda
    assert config.ham_address_to_xy_label(3) == "2x1"
    assert config.ham_address_to_xy_label(5) == "0x1"


def test_testcase_path(config, scenario_dir):
    assert config.get_testcase_path() == str(scenario_dir).rstrip("/")
