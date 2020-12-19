import discord


class Song:
    def __init__(self, title: str, url: str) -> None:
        self.__title = title
        self.__url = url

    @property
    def title(self) -> str:
        return self.__title

    @property
    def url(self) -> str:
        return self.__url

    def new_source(self, **kwargs):
        return discord.FFmpegPCMAudio(self.__url, **kwargs)
