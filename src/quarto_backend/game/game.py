import time
import uuid

from quarto_lib import Cell, Piece, Turn
from quarto_lib import Game as QuartoGame


class Game:
    def __init__(self):
        self._id = uuid.uuid4()
        self._players: list[str | None] = [None, None]
        self._game = QuartoGame()
        self._start_timestamp = None

    @property
    def id(self) -> str:
        return str(self._id)

    @property
    def players(self) -> list[str | None]:
        return self._players.copy()

    @property
    def has_started(self) -> bool:
        return self._start_timestamp is not None

    @property
    def current_player(self) -> str | None:
        if not self.has_started:
            return None
        return self._players[self._game.current_player]

    @property
    def current_turn(self) -> Turn:
        return self._game.current_turn

    @property
    def board(self) -> list[list[Piece | None]]:
        return self._game.board

    @property
    def available_pieces(self) -> list[Piece]:
        return self._game.available_pieces

    def is_full(self) -> bool:
        return all(player is not None for player in self._players)

    def is_empty(self) -> bool:
        return all(player is None for player in self._players)

    def join(self, player_id: str):
        if player_id in self._players:
            raise ValueError(f"Player {player_id} is already in the game.")
        if self.is_full():
            raise ValueError("Game is full, cannot join more players.")
        for i in range(len(self._players)):
            if self._players[i] is None:
                self._players[i] = player_id
                break

    def has_player(self, player_id: str) -> bool:
        return player_id in self._players

    def leave(self, player_id: str):
        if player_id not in self._players:
            raise ValueError(f"Player {player_id} is not in the game.")
        for i in range(len(self._players)):
            if self._players[i] == player_id:
                self._players[i] = None
                break

    def start(self):
        if not self.is_full():
            raise ValueError("Game cannot start, not enough players.")
        if self._start_timestamp is not None:
            return

        self._start_timestamp = time.time()
        self._players = sorted(self._players, key=lambda _: uuid.uuid4())

    def choose_piece(self, piece: Piece):
        self._game.choose_piece(piece)

    def place_piece(self, cell: Cell):
        self._game.place_piece(cell)

    @property
    def current_piece(self) -> Piece | None:
        return self._game.current_piece

    @property
    def winner(self) -> str | None:
        if self._game.winner is None:
            return None
        return self._players[self._game.winner]
