"""Tests for the emulator application.

Reset localnet before running these tests.
"""

from algokit_utils import Account

import emu.utils as utils
from smart_contracts.artifacts.emulator.client import EmulatorClient

# def test_says_hello(hello_world_client: HelloWorldClient) -> None:
#     result = hello_world_client.hello(name="World")

#     assert result.return_value == "Hello, World"


def test_boostrap(app_client: EmulatorClient, creator: Account) -> None:
    """Test bootstrap_application()."""

    seed_tws = utils.create_seed_txn_with_signer(app_client.algod_client, app_client, creator)

    app_id = utils.bootstrap_application(app_client, seed_tws)

    assert isinstance(app_id, int) and app_id > 0
