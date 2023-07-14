import base64
import typing

def http_basic_auth_headers(username: str, password: str) -> typing.Dict[str, str]:
    return {
        "Authorization": f"Basic {base64_encode_str(f'{username}:{password}')}",
    }

def base64_encode_str(plaintext: str) -> str:
    return base64.b64encode(plaintext.encode("utf-8")).decode("ascii")
