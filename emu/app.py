import asyncio

import algokit_utils
from algokit_utils import (
    Account,
    opt_in,
)
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient
from dotenv import set_key
from rich import print
from rich.pretty import pprint
from rich.table import Column, Table

from emu import utils
from emu.models import EmuState
from smart_contracts.artifacts.emulator.client import EmulatorClient


def deploy_app(
    emu_env: dict[str, str | None],
    creator: Account,
    algod_client: AlgodClient,
    indexer_client: IndexerClient,
) -> EmulatorClient:
    """Deploy and bootstrap the application, opt into the EMU asset, set env vars, and return the app client.

    Args:
        emu_env (dict[str, str  |  None]): Dict of emulator environment variables.
        creator (Account): The creator's account.
        algod_client (AlgodClient): Algod client.
        indexer_client (IndexerClient): Indexer client.

    Raises:
        ValueError: If APP_ID is already set in .env.emu.

    Returns:
        EmulatorClient: The emulator app client.
    """

    if "APP_ID" in emu_env:
        raise ValueError(f"APP_ID already set in .env.emu: {emu_env['APP_ID']}")

    app_client = EmulatorClient(
        algod_client,
        creator=creator,
        indexer_client=indexer_client,
    )
    app_client.deploy(
        on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
        on_update=algokit_utils.OnUpdate.AppendApp,
    )
    asset_id = utils.bootstrap_application(
        app_client, utils.create_seed_txn_with_signer(algod_client, app_client, creator)
    )
    not utils.is_opted_in(algod_client, creator, asset_id) and opt_in(algod_client, creator, [asset_id])

    set_key(".env.emu", "CREATOR", creator.address)
    set_key(".env.emu", "APP_ID", str(app_client.app_id))
    set_key(".env.emu", "APP_ADDRESS", str(app_client.app_address))
    set_key(".env.emu", "ASSET_ID", str(asset_id))
    return app_client


def get_app_client(
    account: Account,
    emu_env: dict[str, str | None],
    algod_client: AlgodClient,
    indexer_client: IndexerClient,
) -> EmulatorClient:
    """Returns an emulator app client.

    Args:
        emu_env (dict[str, str  |  None]): Dict of emulator environment variables.
        algod_client (AlgodClient): Algod client.
        indexer_client (IndexerClient): Indexer client.

    Raises:
        ValueError: If APP_ID is not found in .env.emu.

    Returns:
        EmulatorClient: The emulator app client.
    """
    if "APP_ID" not in emu_env:
        raise ValueError("APP_ID not found in .env.emu")
    return EmulatorClient(
        signer=account,
        app_id=int(emu_env["APP_ID"]),
        algod_client=algod_client,
        indexer_client=indexer_client,
    )


def print_state(state: EmuState) -> None:
    """Prints the state of the emulator application.

    Args:
        state (EmuState): The emulator app state.
    """
    table = Table(
        Column("block_height"),
        Column("block_hash", style="magenta"),
        Column("coinbase", style="yellow"),
        Column("prev_retarget_time", style="blue"),
        Column("time", style="green"),
        Column("target", style="bright_cyan"),
    )
    table.add_row(
        state.block_height.__str__(),
        state.block_hash.hex(),
        state.coinbase.hex(),
        state.prev_retarget_time.isoformat(),
        state.time.isoformat(),
        state.target.hex(),
    )
    print(table)


def read_latest_block(app_client: EmulatorClient) -> EmuState | None:
    """Utility function to print and return the latest block.

    Args:
        app_client (EmulatorClient): The emulator app client.

    Returns:
        EmuState | None: The emulator state.
    """
    state = utils.fetch_state(app_client)
    pprint("Latest block:")
    print_state(state)
    return state


def mine(
    algod_client: AlgodClient,
    app_client: EmulatorClient,
    asset_id: int,
    nonce: int,
    coinbase: bytes,
) -> int:
    """Mines a block.

    Args:
        algod_client (AlgodClient): The Algod client.
        app_client (EmulatorClient): The emulator app client.
        asset_id (int): The asset ID.
        nonce (int): The nonce.
        coinbase (bytes): The coinbase.

    Returns:
        int: The amount rewarded if successful.
    """

    tp = utils.get_mining_txn_params(algod_client, asset_id)
    return app_client.mine(nonce=nonce, coinbase=coinbase, transaction_parameters=tp).return_value


async def consumer(
    app_client: EmulatorClient,
    algod_client: AlgodClient,
    asset_id: int,
    coinbase: bytes,
    state: EmuState,
) -> None:
    """Consumes the state and mines the next block.

    Args:
        app_client (EmulatorClient): The emulator app client.
        algod_client (AlgodClient): The Algod client.
        asset_id (int): EMU asset ID.
        coinbase (bytes): The coinbase.
        state (EmuState): The emulator state.
    """

    nonce = utils.find_nonce(state, coinbase)
    if isinstance(nonce, int):
        reward = mine(algod_client, app_client, asset_id, nonce, coinbase)
        pprint(f"Block mined! Reward: {reward}")


async def producer(
    app_client: EmulatorClient,
    algod_client: AlgodClient,
    asset_id: int,
    coinbase: bytes,
    state: EmuState | None = None,
) -> None:
    """Async task producer.

    Fetches the state from the emulator app every 10 seconds.
    If the state has changed, it cancels the previous task (if it exists),
    and creates a new task to mine the next block.

    Args:
        app_client (EmulatorClient): The emulator app client.
        algod_client (AlgodClient): The Algod client.
        asset_id (int): EMU asset ID.
        coinbase (bytes): The coinbase.
        state (EmuState | None, optional): The emulator state. Defaults to None.
    """
    prev_state: EmuState | None = None
    task = None
    while True:
        state = utils.fetch_state(app_client)
        if prev_state is None or state.block_height > prev_state.block_height:
            if task and not task.done():
                task.cancel()
            pprint("New block found!")
            print_state(state)
            task = asyncio.create_task(consumer(app_client, algod_client, asset_id, coinbase, state))
            try:
                await asyncio.wait_for(task, timeout=10)
            except asyncio.TimeoutError:
                continue
        prev_state = state
