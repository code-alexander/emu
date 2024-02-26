import asyncio

import typer
from dotenv import dotenv_values, set_key
from dotenv_vault import load_dotenv

from emu import app, utils

cli = typer.Typer()

load_dotenv()
emu_env = dotenv_values(".env.emu")


@cli.command()
def network(network: str):
    """Set the Algorand network.

    Args:
        network (str): Must be 'localnet', 'testnet', or 'mainnet'.

    Raises:
        ValueError: If the network name is invalid.
    """
    if network not in {"localnet", "testnet", "mainnet"}:
        raise ValueError("Invalid network")
    set_key(".env.emu", "NETWORK", network)
    print(f"Network set to {network}")


@cli.command()
def deploy():
    """Deploy the application."""
    algod_client, indexer_client, account = utils.get_clients(emu_env)
    app.deploy_app(
        emu_env=emu_env,
        creator=account,
        algod_client=algod_client,
        indexer_client=indexer_client,
    )


@cli.command()
def mine():
    """Mine a new block."""
    algod_client, indexer_client, account = utils.get_clients(emu_env)
    app_client = app.get_app_client(account, emu_env, algod_client, indexer_client)

    async def main():
        await app.producer(
            app_client=app_client,
            algod_client=algod_client,
            asset_id=emu_env["ASSET_ID"],
            coinbase=account.address.encode("utf-8"),
            state=None,
        )

    asyncio.run(main())


@cli.command()
def chain():
    """Fetch the latest block."""
    algod_client, indexer_client, account = utils.get_clients(emu_env)
    app_client = app.get_app_client(account, emu_env, algod_client, indexer_client)
    app.read_latest_block(app_client)


if __name__ == "__main__":
    cli()
