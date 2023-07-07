import time
import click
import requests
import tomllib
import config
from urllib.parse import quote_plus
from uuid import uuid4
from typing import Any
import json


def read_config(option: str) -> tuple[Any]:
    return config.cfg[option]


def connect(client_id: str, secret: str, redirect_uri: str, scopes: list[str]):
    state = uuid4().hex
    twitch_url = "https://id.twitch.tv/oauth2"
    url = (
        f"{twitch_url}/authorize?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={quote_plus(' '.join(scopes))}"
        f"&state={state}"
    )
    print(f"Please visit: {url}")
    code = input("Insert code: ")
    data = {
        "code": code,
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": secret,
        "redirect_uri": redirect_uri,
    }
    token = requests.post(f"{twitch_url}/token", data=data).json()
    print(token)



@click.command()
@click.argument("message")
@click.option("--client-id", "-c", help="Client ID for authentication.")
@click.option(
    "--scope",
    "-s",
    multiple=True,
    help="Scope to use. Can be passed multiple times for more than one scope.",
)
@click.option("--secret", "-x", help="Client Secret.")
def cli(message, client_id, scope, secret):
    """
    Sends a message
    """
    twitch_config = read_config("twitch")
    redirect_uri = twitch_config["redirect_uri"]
    if client_id is None:
        client_id = twitch_config["client_id"]
    if not scope:
        scope = twitch_config["scopes"]
    if secret is None:
        secret = twitch_config["client_secret"]
    connect(client_id, secret, redirect_uri, scope)
    click.echo(f"Hello I'm a bot saying {message}")


def main():
    cli()


if __name__ == "__main__":
    main()
