import logging
import random
import time
import uuid

from quarto_lib import Cell, GameState, Piece, Turn
from quarto_lib import Game as QuartoGame

from quarto_backend.game.agent_handler import AgentHandler

logger = logging.getLogger(__name__)


class Game:
    def __init__(self):
        self._id = uuid.uuid4()
        self._players: list[str | None] = [None, None]
        self._game = QuartoGame()
        self._start_timestamp = None
        self._agent: AgentHandler | None = None

    @property
    def id(self) -> str:
        return str(self._id)

    @property
    def players(self) -> list[str | None]:
        return self._players.copy()

    @property
    def is_started(self) -> bool:
        return self._start_timestamp is not None

    @property
    def current_player(self) -> str | None:
        if not self.is_started:
            return None
        return self._players[self._game.current_player]

    @property
    def is_pve(self) -> bool:
        return self._agent is not None

    @property
    def current_turn(self) -> Turn:
        return self._game.current_turn

    @property
    def board(self) -> list[list[Piece | None]]:
        return self._game.board

    @property
    def available_pieces(self) -> list[Piece]:
        return self._game.available_pieces

    @property
    def available_cells(self) -> list[Cell]:
        return self._game.available_cells

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

    async def setup_pve(self, agent_endpoint: str):
        if self.is_full():
            raise ValueError("Game is full, cannot add more players.")
        agent = await AgentHandler(agent_endpoint).initialize()
        self.join(agent.identifier)
        self._agent = agent

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

    async def agent_turn(self):
        if self._agent is None:
            raise ValueError("No agent configured for this game.")
        if self.current_player != self._agent.identifier:
            raise ValueError("It's not the agent's turn.")

        if self.current_piece is None:
            logger.debug("Agent is choosing the initial piece.")
            try:
                response = await self._agent.choose_initial_piece()
                logger.debug(f"Agent chose piece: {response.piece}")
                self.choose_piece(response.piece)
            except RuntimeError as e:
                logger.error(f"Agent error during initial piece selection: {e}")
                self.choose_piece(random.choice(self.available_pieces))

            return

        logger.debug("Agent is completing its turn.")
        try:
            response = await self._agent.complete_turn(GameState(current_piece=self.current_piece, board=self.board))
            logger.debug(f"Agent completed turn with response: {response}")
            self.place_piece(response.cell)
            if response.piece is not None:
                self.choose_piece(response.piece)
        except RuntimeError as e:
            logger.error(f"Agent error during turn completion: {e}")
            self.place_piece(random.choice(self.available_cells))
            if self.winner is None:
                self.choose_piece(random.choice(self.available_pieces))

    @property
    def current_piece(self) -> Piece | None:
        return self._game.current_piece

    @property
    def winner(self) -> str | None:
        if self._game.winner is None:
            return None
        return self._players[self._game.winner]
