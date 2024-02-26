from puyapy import (
    Account,
    ARC4Contract,
    Asset,
    BigUInt,
    Bytes,
    Global,
    Txn,
    UInt64,
    arc4,
    gtxn,
    itxn,
    log,
    op,
    subroutine,
)

DECIMALS = 8
# https://github.com/bitcoin/bitcoin/blob/master/src/consensus/amount.h
# /** The amount of satoshis in one BTC. */
# static constexpr CAmount COIN = 100000000;
COIN = 100_000_000  # 10**DECIMALS
# static constexpr CAmount MAX_MONEY = 21000000 * COIN;
# inline bool MoneyRange(const CAmount& nValue) { return (nValue >= 0 && nValue <= MAX_MONEY); }
MAX_MONEY = 2_100_000_000_000_000  # 21_000_000 * COIN
GENESIS_BLOCK_HEIGHT = 0
# https://github.com/bitcoin/bitcoin/blob/bdddf364c9a6f80e3bfcf45ab1ae54f9eab5811b/src/kernel/chainparams.cpp#L29
# consensus.hashGenesisBlock == uint256S("0x000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f")
GENESIS_BLOCK_HASH = 0x000000000019D6689C085AE165831E934FF763AE46A2A6C172B3F1B60A8CE26F
# https://github.com/bitcoin/bitcoin/blob/45b2a91897ca8f4a3e0c1adcfb30cf570971da4e/src/kernel/chainparams.cpp#L77
# consensus.nSubsidyHalvingInterval = 210000
SUBSIDY_HALVING_INTERVAL = 210_000
# CAmount nSubsidy = 50 * COIN;
SUBSIDY = 50 * COIN
# consensus.powLimit = uint256S("00000000ffffffffffffffffffffffffffffffffffffffffffffffffffffffff");
# https://github.com/bitcoin/bitcoin/blob/c265aad5b52bf7b1b1e3cc38d04812caa001ba76/src/kernel/chainparams.cpp#L89
# Note: We are raising the target to make it easier to mine blocks.
POW_LIMIT = 0x3FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
# Spanning 1 hour
POW_TARGET_TIMESPAN = 60 * 60
# Aim for 1 block every 10 seconds
POW_TARGET_SPACING = 10
SMALLEST_TIMESPAN = POW_TARGET_TIMESPAN // 4
LARGEST_TIMESPAN = POW_TARGET_TIMESPAN * 4
# Adjust the difficulty every 360 blocks
DIFFICULTY_ADJUSTMENT_INTERVAL = POW_TARGET_TIMESPAN // POW_TARGET_SPACING


@subroutine
def least(a: UInt64, b: UInt64) -> UInt64:
    """Return the lesser of two values.

    Args:
        a (UInt64): The first number.
        b (UInt64): The second number.

    Returns:
        UInt64: The lesser of `a` and `b`.
    """
    return a if a < b else b


@subroutine
def greatest(a: UInt64, b: UInt64) -> UInt64:
    """Return the greater of two values.

    Args:
        a (UInt64): The first number.
        b (UInt64): The second number.

    Returns:
        UInt64: The greater of `a` and `b`.
    """
    return a if a > b else b


@subroutine
def clamp(value: UInt64, lower_bound: UInt64, upper_bound: UInt64) -> UInt64:
    """Clamp a value to the range [lower_bound, upper_bound].

    Args:
        value (UInt64): The value to clamp.
        lower_bound (UInt64): The lower bound.
        upper_bound (UInt64): The upper bound.

    Returns:
        UInt64: The clamped value.
    """
    return least(greatest(value, lower_bound), upper_bound)


@subroutine
def transfer_asset(receiver: Account, asset: Asset, amount: UInt64) -> Bytes:
    """Submits an inner transaction to transfer an asset.

    Args:
        receiver (Account): The receiver of the asset.
        asset (Asset): The asset to transfer.
        amount (UInt64): The amount to transfer.

    Returns:
        Bytes: The transaction ID.
    """
    return (
        itxn.AssetTransfer(
            xfer_asset=asset,
            asset_amount=amount,
            asset_receiver=receiver,
            fee=0,
        )
        .submit()
        .txn_id
    )


class Emulator(ARC4Contract):
    def __init__(self) -> None:
        self.creator = Txn.sender
        self.asa = Asset(0)
        self.block_height = UInt64(GENESIS_BLOCK_HEIGHT)
        self.block_hash = arc4.UInt256(GENESIS_BLOCK_HASH)
        self.coinbase = Bytes()
        self.prev_retarget_time = UInt64(0)
        self.time = UInt64(0)
        self.target = BigUInt(POW_LIMIT)

    @subroutine
    def is_bootstrapped(self) -> bool:
        """Check if the application has been bootstrapped.

        The __bool__() method of puyapy.Asset returns True if the asset_id is not 0.
        Reference: https://algorandfoundation.github.io/puya/api-puyapy.html#puyapy.Asset

        Returns:
            bool: True if the application has been bootstrapped, else False.
        """
        return bool(self.asa)

    @arc4.abimethod()
    def bootstrap(self, seed: gtxn.PaymentTransaction) -> UInt64:
        """Bootstrap the application.

        This method is idempotent.
        It creates the asset and opts the contract account into the asset.

        Args:
            seed (gtxn.PaymentTransaction): Initial payment transaction to the app account.

        Returns:
            UInt64: The ID of the asset created.
        """
        assert not self.is_bootstrapped(), "Application has already been bootstrapped"
        assert Txn.sender == self.creator, "Only the creator may call this method"
        assert seed.receiver == Global.current_application_address, "Receiver must be app address"
        assert Global.group_size == 2, "Group size must be 2"
        assert seed.amount >= 300_000, "Amount must be >= 3 Algos"  # 0.3 Algos
        self.asa = self.create_asset()
        self.prev_retarget_time = self.time = Global.latest_timestamp
        return self.asa.asset_id

    @subroutine
    def should_adjust_difficulty(self) -> arc4.Bool:
        """Checks whether the difficulty target should be adjusted.

        Returns:
            arc4.Bool: True if the difficulty target should be adjusted, False otherwise.
        """
        return arc4.Bool(self.block_height % DIFFICULTY_ADJUSTMENT_INTERVAL == 0)

    @subroutine
    def calculate_next_work_required(self) -> BigUInt:
        """Calculate the next POW target.

        Returns:
            BigUInt: The new target.
        """
        timespan = clamp(
            value=self.time - self.prev_retarget_time,
            lower_bound=UInt64(SMALLEST_TIMESPAN),
            upper_bound=UInt64(LARGEST_TIMESPAN),
        )
        new_target = self.target * (timespan * 1000 // POW_TARGET_TIMESPAN) // 1000
        return new_target if new_target < POW_LIMIT else BigUInt(POW_LIMIT)

    @subroutine
    def get_block_subsidy(self) -> UInt64:
        """Get block subsidy (mining reward).

        Returns:
            UInt64: The subsidy amount.
        """
        halvings = self.block_height // SUBSIDY_HALVING_INTERVAL
        # Force block reward to zero when right shift is undefined.
        return UInt64(0) if halvings >= 64 else SUBSIDY >> halvings

    @subroutine
    def create_asset(self) -> Asset:
        """Submits an inner transaction to create the asset.

        Returns:
            Asset: The asset created.
        """
        return (
            itxn.AssetConfig(
                asset_name=b"EMU",
                unit_name=b"EMUSHIS",
                total=MAX_MONEY,
                decimals=DECIMALS,
                manager=Global.current_application_address,
                reserve=Global.current_application_address,
                fee=0,
            )
            .submit()
            .created_asset
        )

    @subroutine
    def reward_miner(self) -> UInt64:
        """Reward the miner.

        Returns:
            UInt64: The reward amount.
        """
        return (
            itxn.AssetTransfer(
                xfer_asset=self.asa,
                asset_amount=self.get_block_subsidy(),
                asset_receiver=Txn.sender,
                fee=0,
            )
            .submit()
            .asset_amount
        )

    @arc4.abimethod()
    def mine(self, nonce: arc4.UInt64, coinbase: Bytes) -> UInt64:
        """Mine a block.

        Args:
            nonce (arc4.UInt64): The nonce.
            coinbase (Bytes): The coinbase.

        Returns:
            UInt64: The amount rewarded to the miner.
        """
        assert self.is_bootstrapped(), "Application not bootstrapped"

        proposed_block_hash = BigUInt.from_bytes(op.sha256(op.sha256(self.block_hash.bytes + nonce.bytes + coinbase)))
        assert proposed_block_hash < self.target, "Invalid block"

        current_time = Global.latest_timestamp
        self.block_height += 1
        self.block_hash = arc4.UInt256(proposed_block_hash)
        self.coinbase = coinbase  # Store this in state just for fun
        self.time = current_time
        if self.should_adjust_difficulty():
            next_work = self.calculate_next_work_required()
            log(
                "retargeted_at",
                current_time,
                "prev_retarget_time",
                self.prev_retarget_time,
                "prev_target",
                self.target,
                "new_target",
                next_work,
                sep=b"\x1F",
            )
            self.prev_retarget_time = current_time
            self.target = next_work
        reward = self.reward_miner()
        log(
            "miner",
            Txn.sender.bytes,
            "reward",
            reward,
            sep=b"\x1F",
        )
        return reward
