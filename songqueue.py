from typing import Union
from song import Song
import random


class SongQueue:
    def __init__(self):
        self.__now_playing: Union[None, Song] = None
        self.__queue: list[Song] = list()
        self.__loop: bool = False


    @property
    def now_playing(self) -> Union[None, Song]:
        return self.__now_playing

    
    @property
    def queue(self) -> list[Song]:
        return self.__queue[:]


    @property
    def loop(self) -> bool:
        return self.__loop


    @loop.setter
    def loop(self, value: bool) -> None:
        self.__loop = value


    def is_empty(self) -> bool:
        return len(self.__queue) == 0


    def add(self, song: Song) -> None:
        self.__queue.append(song)

    
    def remove(self, start: int, end: int) -> Union[tuple[Song], None]:
        if len(self.__queue) > start >= 0 and len(self.__queue) > end >= 0 and end >= start:
            return tuple([self.__queue.pop(start) for i in range(end - start + 1)])
        return None

    
    def clear(self) -> None:
        self.__queue.clear()


    def shuffle(self) -> None:
        random.shuffle(self.__queue)

    
    def next(self) -> None:
        if self.__loop and self.__now_playing is not None:
            return

        if not self.is_empty():
            self.__now_playing = self.__queue.pop(0)
            return

        if self.__now_playing:
            self.__now_playing = None
