from typing import Union
from song import Song
import random


class SongQueue:
    def __init__(self):
        self.__now_playing: Union[None, Song] = None
        self.__queue: list[Song] = list()


    @property
    def now_playing(self) -> Union[None, Song]:
        return self.__now_playing

    
    @property
    def queue(self) -> list[Song]:
        return self.__queue[:]


    def is_empty(self) -> bool:
        return len(self.__queue) == 0


    def add(self, song: Song) -> None:
        self.__queue.append(song)

    
    def remove(self, index: int) -> Union[Song, None]:
        if len(self.__queue) > index >= 0:
            return self.__queue.pop(index)
        return None

    
    def clear(self) -> None:
        self.__queue.clear()

    
    def next(self) -> None:
        if self.is_empty():
            if self.__now_playing:
                self.__now_playing = None
            else:
                raise Exception("Queue is already depleted!")
        else:
            self.__now_playing = self.__queue.pop(0)


    def shuffle(self) -> None:
        if self.is_empty():
            raise Exception("Cannot shuffle empty queue!")

        random.shuffle(self.__queue)
