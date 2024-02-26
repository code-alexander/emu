"""Test the emu utility functions."""

from datetime import datetime
from types import SimpleNamespace

from algokit_utils import Account, TransactionParameters
from algosdk.atomic_transaction_composer import (
    TransactionWithSigner,
)
from algosdk.transaction import SuggestedParams
from algosdk.v2client.algod import AlgodClient

import emu.utils as utils
from emu.models import EmuState
from smart_contracts.artifacts.emulator.client import ByteReader, EmulatorClient


def test_get_suggested_params() -> None:
    """Test get_suggested_params()."""

    class MockAlgodClient:
        @staticmethod
        def suggested_params() -> SuggestedParams:
            return SuggestedParams(
                first=3,
                last=1003,
                gh="fG7CxdNhG8li/KCRqYM+qmny/w13I7kiDn3rlirw9qA=",
                gen="dockernet-v1",
                fee=0,
                flat_fee=False,
                consensus_version="future",
                min_fee=1000,
            )

    algod_client = MockAlgodClient()
    params = utils.get_suggested_params(algod_client)
    assert isinstance(params, SuggestedParams)
    assert params.fee > params.min_fee
    assert params.flat_fee is True


def test_create_seed_txn_with_signer(algod_client: AlgodClient, app_client: EmulatorClient) -> None:
    """Test create_seed_txn_with_signer()."""
    account = Account.new_account()
    tws = utils.create_seed_txn_with_signer(algod_client, app_client, account)
    assert isinstance(tws, TransactionWithSigner)


def test_get_mining_txn_params(algod_client: AlgodClient) -> None:
    """Test get_mining_params()."""
    tp = utils.get_mining_txn_params(algod_client, asset_id=1)
    assert isinstance(tp, TransactionParameters)


def test_is_opted_in() -> None:
    """Test is_opted_in()."""
    account = Account.new_account()

    class MockAlgodClient:
        @staticmethod
        def account_info(address: str) -> dict[str, list[dict[str, int]]]:
            return {"assets": [{"asset-id": 1}]}

    algod_client = MockAlgodClient()
    assert utils.is_opted_in(algod_client, account, 1) is True


def test_btoi() -> None:
    """Test btoi()."""
    assert utils.btoi(b"\x00\x00\x00\x00\x00\x00\x00\x03") == 3


def test_itob() -> None:
    """Test itob()."""
    assert utils.itob(3) == b"\x00\x00\x00\x00\x00\x00\x00\x03"


def test_find_nonce() -> None:
    """Test find_nonce()."""
    state = EmuState(
        block_height=0,
        block_hash=b"\x00\x00\x00\x00\x00\x19\xd6h\x9c\x08Z\xe1e\x83\x1e\x93O\xf7c\xaeF\xa2\xa6\xc1r\xb3\xf1\xb6\n\x8c\xe2o",
        coinbase=b"",
        prev_retarget_time=datetime(2021, 1, 1),
        time=datetime(2021, 1, 1),
        target=b"\x00?\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff",
    )
    assert utils.find_nonce(state, b"") == 64


def test_fetch_state() -> None:
    """Test fetch_state()."""

    class MockAppClient:
        @staticmethod
        def get_global_state() -> SimpleNamespace:
            return SimpleNamespace(
                block_height=10,
                block_hash=ByteReader(
                    b"\x00\x00\x00\x00\x00\x19\xd6h\x9c\x08Z\xe1e\x83\x1e\x93O\xf7c\xaeF\xa2\xa6\xc1r\xb3\xf1\xb6\n\x8c\xe2o"
                ),
                coinbase=ByteReader(b""),
                prev_retarget_time=1640995200,
                time=1640995200,
                target=ByteReader(
                    b"\x00?\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff",
                ),
            )

    app_client = MockAppClient()

    # Call the fetch_state function
    state = utils.fetch_state(app_client)

    # Assert the returned value is an instance of EmuState
    assert isinstance(state, EmuState)

    # Assert the values of the EmuState object
    assert state.block_height == 10
    assert (
        state.block_hash
        == b"\x00\x00\x00\x00\x00\x19\xd6h\x9c\x08Z\xe1e\x83\x1e\x93O\xf7c\xaeF\xa2\xa6\xc1r\xb3\xf1\xb6\n\x8c\xe2o"
    )
    assert state.coinbase == b""
    assert state.prev_retarget_time == datetime.fromtimestamp(1640995200)
    assert state.time == datetime.fromtimestamp(1640995200)
    assert (
        state.target
        == b"\x00?\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"  # noqa: E501
    )


def test_bootstrap_application(creator: Account) -> None:
    """Test bootstrap_application()."""

    class MockAppClient:
        @staticmethod
        def get_global_state() -> SimpleNamespace:
            return SimpleNamespace(asa=1001)

        @staticmethod
        def bootstrap(seed: TransactionWithSigner) -> SimpleNamespace:
            return SimpleNamespace(return_value=1001)

        @property
        def app_id(self) -> int:
            """Mock app id.

            Returns:
                int: The app id.
            """
            return 1027

        @property
        def app_address(self) -> str:
            """Mock app address.

            Returns:
                str: The app address.
            """
            return creator.address

    class MockAlgodClient:
        @staticmethod
        def suggested_params() -> SuggestedParams:
            return SuggestedParams(
                first=3,
                last=1003,
                gh="fG7CxdNhG8li/KCRqYM+qmny/w13I7kiDn3rlirw9qA=",
                gen="dockernet-v1",
                fee=0,
                flat_fee=False,
                consensus_version="future",
                min_fee=1000,
            )

    algod_client = MockAlgodClient()

    app_client = MockAppClient()
    algod_client = MockAlgodClient()

    tws = utils.create_seed_txn_with_signer(algod_client, app_client, creator)

    assert utils.bootstrap_application(app_client, tws) == 1001


def test_bootstrap_application_idempotence(creator: Account) -> None:
    """Test that the bootstrap_application() function is idempotent."""

    class MockAppClient:
        @staticmethod
        def get_global_state() -> SimpleNamespace:
            return SimpleNamespace(asa=1001)

        @property
        def app_id(self) -> int:
            """Mock app id.

            Returns:
                int: The app id.
            """
            return 1027

        @property
        def app_address(self) -> str:
            """Mock app address.

            Returns:
                str: The app address.
            """
            return creator.address

    class MockAlgodClient:
        @staticmethod
        def suggested_params() -> SuggestedParams:
            return SuggestedParams(
                first=3,
                last=1003,
                gh="fG7CxdNhG8li/KCRqYM+qmny/w13I7kiDn3rlirw9qA=",
                gen="dockernet-v1",
                fee=0,
                flat_fee=False,
                consensus_version="future",
                min_fee=1000,
            )

    algod_client = MockAlgodClient()

    app_client = MockAppClient()
    algod_client = MockAlgodClient()

    tws = utils.create_seed_txn_with_signer(algod_client, app_client, creator)

    assert utils.bootstrap_application(app_client, tws) == 1001
