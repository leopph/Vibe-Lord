from discord import FFmpegPCMAudio


class Song:
    def __init__(self, title: str, length: int, url: str) -> None:
        self.__title = title
        self.__url = url
        self.__length = length

    @property
    def title(self) -> str:
        return self.__title

    @property
    def length(self) -> int:
        return self.__length

    @property
    def url(self) -> str:
        return self.__url

    def new_source(self, **kwargs):
        return FFmpegPCMAudio(self.__url, **kwargs)
