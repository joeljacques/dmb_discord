import re


def valid_discord(string: str) -> bool:
    return re.match(".*#[0-9]{4}", string) is not None