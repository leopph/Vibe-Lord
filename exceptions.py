from discord.ext.commands import CommandError


class CheckFailedError(CommandError):
    def __init__(self, text: str) -> None:
        self._text = text

    def __str__(self) -> str:
        return self._text