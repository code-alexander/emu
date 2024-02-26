"""Utility functions for emu."""

from datetime import datetime
from hashlib import sha256

from algokit_utils import (
    Account,
    TransactionParameters,
    get_account,
    get_algod_client,
    get_algonode_config,
    get_default_localnet_config,
    get_indexer_client,
)
from algosdk.atomic_transaction_composer import (
    AccountTransactionSigner,
    TransactionWithSigner,
)
from algosdk.transaction import PaymentTxn, SuggestedParams
from algosdk.v2client.algod import AlgodClient

from emu.models import EmuState
from smart_contracts.artifacts.emulator.client import EmulatorClient


def get_suggested_params(algod_client: AlgodClient) -> SuggestedParams:
    """Gets suggested parameters for a transaction.

    Args:
        algod_client (AlgodClient): The Algod client.

    Returns:
        SuggestedParams: The suggested parameters.
    """
    sp = algod_client.suggested_params()
    sp.fee = sp.min_fee * 5
    sp.flat_fee = True
    return sp


def create_seed_txn_with_signer(
    algod_client: AlgodClient,
    app_client: EmulatorClient,
    account: Account,
) -> TransactionWithSigner:
    """Creates a 'transaction with signer' object for seeding the application.

    Args:
        algod_client (AlgodClient): The Algod client.
        app_client (EmulatorClient): The emulator app client.
        account (Account): The account that will fund the application creation.

    Returns:
        TransactionWithSigner: The transaction with signer object.
    """
    signer = AccountTransactionSigner(account.private_key)
    sp = get_suggested_params(algod_client)
    ptxn = PaymentTxn(account.address, sp, app_client.app_address, 300_000)
    return TransactionWithSigner(ptxn, signer)


def get_mining_txn_params(algod_client: AlgodClient, asset_id: int) -> TransactionParameters:
    """Gets transaction parameters for mining.

    Args:
        algod_client (AlgodClient): The Algod client.
        asset_id (int): The asset ID.

    Returns:
        TransactionParameters: The transaction parameters.
    """

    return TransactionParameters(
        suggested_params=get_suggested_params(algod_client),
        foreign_assets=[asset_id],
    )


def is_opted_in(algod_client: AlgodClient, account: Account, asset_id: int) -> bool:
    """Check if the account is opted into the asset.

    Args:
        algod_client (AlgodClient): The Algod client.
        account (Account): The account to check.
        asset_id (int): The asset ID to check.

    Returns:
        bool: True if the account is opted in, else False.
    """
    account_info = algod_client.account_info(account.address)
    return any(x["asset-id"] == asset_id for x in account_info["assets"])


def btoi(b: bytes) -> int:
    """Converts bytes to integer.

    Args:
        b (bytes): The bytes to convert.

    Returns:
        int: The integer.
    """
    return int.from_bytes(b, byteorder="big")


def itob(n: int) -> bytes:
    """Converts integer to bytes.

    Args:
        n (int): The integer to convert.

    Returns:
        bytes: The bytes.
    """
    return n.to_bytes(length=8, byteorder="big")


def find_nonce(state: EmuState, coinbase: bytes) -> int | None:
    """Finds a nonce for the block.

    Args:
        state (EmuState): The emulator state.
        coinbase (bytes): The coinbase.

    Returns:
        int | None: The nonce if found, else None.
    """
    for nonce in range(2**64):
        attempt = sha256(sha256(state.block_hash + itob(nonce) + coinbase).digest()).digest()
        if btoi(attempt) < btoi(state.target):
            return nonce


def fetch_state(app_client: EmulatorClient) -> EmuState:
    """Fetch the latest state of the emulator.

    Args:
        app_client (EmulatorClient): The emulator app client.

    Returns:
        EmuState: The emulator state.
    """
    state = app_client.get_global_state()
    return EmuState(
        block_height=state.block_height,
        block_hash=state.block_hash.as_bytes,
        coinbase=state.coinbase.as_bytes,
        prev_retarget_time=datetime.fromtimestamp(state.prev_retarget_time),
        time=datetime.fromtimestamp(state.time),
        target=state.target.as_bytes,
    )


def bootstrap_application(app_client: EmulatorClient, seed_tws: TransactionWithSigner) -> int | None:
    """Bootstraps the application.

    Args:
        app_client (EmulatorClient): The emulator app client.
        seed_tws (TransactionWithSigner): The seed transaction with signer.

    Returns:
        int | None: The asset ID if the application was bootstrapped, else None.
    """
    state = app_client.get_global_state()
    return state.asa or app_client.bootstrap(seed=seed_tws).return_value


def get_clients(emu_env: dict[str, str]) -> tuple[AlgodClient, AlgodClient, Account]:
    """Get Algod client, Indexer client, and account.

    Args:
        emu_env (dict[str, str]): The emulator environment.

    Returns:
        tuple[AlgodClient, AlgodClient, Account]: The Algod client, Indexer client, and account.
    """

    network = emu_env["NETWORK"]

    if network == "localnet":
        algod_config = get_default_localnet_config("algod")
        indexer_config = get_default_localnet_config("indexer")
    else:
        algod_config = get_algonode_config(network=network, config="algod", token="")
        indexer_config = get_algonode_config(network=network, config="indexer", token="")

    algod_client = get_algod_client(algod_config)
    indexer_client = get_indexer_client(indexer_config)

    account = get_account(client=algod_client, name="ACCOUNT")

    return algod_client, indexer_client, account
