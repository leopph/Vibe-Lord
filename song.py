from discord import FFmpegPCMAudio
from typing import BinaryIO, Union
from io import BytesIO


class Song:
    def __init__(self, title: str, length: int, url: str, img: BytesIO = None) -> None:
        self.__title = title
        self.__url = url
        self.__length = length
        self.__img = img

    @property
    def title(self) -> str:
        return self.__title

    @property
    def length(self) -> int:
        return self.__length

    @property
    def url(self) -> str:
        return self.__url

    @property
    def image(self) -> Union[BytesIO, None]:
        return self.__img

    def new_source(self, **kwargs):
        return FFmpegPCMAudio(self.__url, **kwargs)
