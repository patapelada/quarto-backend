import logging
import os
from enum import Enum
from typing import Literal, TypedDict

import pydantic_socketio
from pydantic import BaseModel
from quarto_lib import Cell, Piece, Turn

from quarto_backend.db import InMemoryDB
from quarto_backend.game.game import Game

allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
agent = os.getenv("AGENT_ENDPOINT", None)

sio = pydantic_socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=allowed_origins)

logger = logging.getLogger(__name__)
db = InMemoryDB[str, Game]()


class PlayerLeftResponse(BaseModel):
    playerId: str


class GameJoinedResponse(BaseModel):
    gameId: str
    players: list[str | None]


class GameStartedResponse(BaseModel):
    gameId: str


class PlayerJoinedResponse(BaseModel):
    gameId: str
    playerId: str


class JoinGameRequest(BaseModel):
    gameId: str


class StartGameRequest(BaseModel):
    gameId: str


class GenericErrorResponse(BaseModel):
    key: str
    message: str


class SelectPieceRequest(BaseModel):
    gameId: str
    piece: Piece


class PlacePieceRequest(BaseModel):
    gameId: str
    cell: Cell


class GameStateUpdateResponse(TypedDict):
    gameId: str
    currentTurn: Literal[0, 1]
    currentPlayerId: str | None
    currentPiece: int | None
    board: list[list[int | None]]
    availablePieces: list[int]
    winnerId: str | None


class Emits(Enum):
    PLAYER_JOINED = "player-joined"
    PLAYER_LEFT = "player-left"
    GAME_JOINED = "game-joined"
    GAME_STARTED = "game-started"
    ERROR = "error"
    GAME_STATE_UPDATED = "game-state-updated"


@sio.event  # type: ignore
async def disconnect(sid: str, reason: str):
    logger.info(f"Client disconnected: {sid}, reason: {reason}")
    games = [game for game in db.list_all().values() if game.has_player(sid)]
    if games:
        for game in games:
            game.leave(sid)
            if game.is_empty():
                db.delete(game.id)
                logger.info(f"Game {game.id} deleted as it is empty.")
            else:
                response = PlayerLeftResponse(playerId=sid)
                await sio.emit(Emits.PLAYER_LEFT.value, response, room=game.id)  # type: ignore
    return True


@sio.event  # type: ignore
async def connect(sid: str, environ: object, auth: object):
    logger.info(f"Client connected: {sid}")
    return True


async def create_game(sid: str) -> Game:
    await disconnect(sid, "Creating new game")

    game = Game()
    game.join(sid)
    db.create(game.id, game)
    await sio.enter_room(sid, game.id)  # type: ignore

    response = GameJoinedResponse(gameId=game.id, players=game.players)
    await sio.emit(Emits.GAME_JOINED.value, response, to=sid)  # type: ignore

    return game


@sio.on("new-game")  # type: ignore
async def create_new_game(sid: str):
    game = await create_game(sid)
    logger.info(f"Game created with ID: {game.id} for client {sid}")


@sio.on("pve")  # type: ignore
async def pve(
    sid: str,
):
    logger.info(f"Client {sid} requested PVE game.")
    if not agent:
        await sio.emit(  # type: ignore
            Emits.ERROR.value,
            GenericErrorResponse(key="ERR_AGENT_NOT_CONFIGURED", message="Agent endpoint not configured"),
            to=sid,
        )
        return
    game = await create_game(sid)
    if game.is_started:
        await sio.emit(  # type: ignore
            Emits.ERROR.value,
            GenericErrorResponse(key="ERR_GAME_ALREADY_STARTED", message="Game has already started"),
            to=sid,
        )
        return

    await game.setup_pve(agent)
    await start_game(sid, StartGameRequest(gameId=game.id))
    if game.current_player != sid:
        await game.agent_turn()
        await emit_game_state_update(game)


@sio.on("matchmaking")  # type: ignore
async def matchmaking(sid: str):
    logger.info(f"Client {sid} requested matchmaking.")
    game = next((game for game in db.list_all().values() if not game.is_full() and not game.has_player(sid)), None)
    if not game:
        await create_new_game(sid)
        return

    await join_game(sid, JoinGameRequest(gameId=game.id))


@sio.on("join-game")  # type: ignore
async def join_game(sid: str, request: JoinGameRequest):
    game = db.read(request.gameId)
    if not game:
        await sio.emit(  # type: ignore
            Emits.ERROR.value, GenericErrorResponse(key="ERR_GAME_NOT_FOUND", message="Game not found"), to=sid
        )
        return
    if game.is_full():
        await sio.emit(Emits.ERROR.value, GenericErrorResponse(key="ERR_GAME_FULL", message="Game is full"), to=sid)  # type: ignore
        return

    game.join(sid)
    await sio.enter_room(sid, game.id)  # type: ignore

    player_response = PlayerJoinedResponse(gameId=game.id, playerId=sid)
    await sio.emit(Emits.PLAYER_JOINED.value, player_response, room=game.id, skip_sid=sid)  # type: ignore

    game_response = GameJoinedResponse(gameId=game.id, players=game.players)
    await sio.emit(Emits.GAME_JOINED.value, game_response, to=sid)  # type: ignore


@sio.on("start-game")  # type: ignore
async def start_game(sid: str, request: StartGameRequest):
    game = db.read(request.gameId)
    if not game:
        await sio.emit(  # type: ignore
            Emits.ERROR.value, GenericErrorResponse(key="ERR_GAME_NOT_FOUND", message="Game not found"), to=sid
        )
        return

    if not game.has_player(sid):
        await sio.emit(  # type: ignore
            Emits.ERROR.value, GenericErrorResponse(key="ERR_NOT_IN_GAME", message="You are not in this game"), to=sid
        )
        return

    if not game.is_full():
        await sio.emit(  # type: ignore
            Emits.ERROR.value, GenericErrorResponse(key="ERR_NO_OPPONENT", message="Game has no opponent"), to=sid
        )
        return

    game.start()
    if game.current_player is None:
        await sio.emit(  # type: ignore
            Emits.ERROR.value,
            GenericErrorResponse(key="ERR_INVALID_STATE", message="Current player is not set"),
            to=sid,
        )
        return
    response = GameStartedResponse(gameId=game.id)
    await sio.emit(Emits.GAME_STARTED.value, response, room=game.id)  # type: ignore
    await emit_game_state_update(game)


@sio.on("select-piece")  # type: ignore
async def select_piece(sid: str, request: SelectPieceRequest):
    game = next((game for game in db.list_all().values() if game.id == request.gameId), None)
    if not game or not game.has_player(sid):
        await sio.emit(  # type: ignore
            Emits.ERROR.value, GenericErrorResponse(key="ERR_GAME_NOT_FOUND", message="Game not found"), to=sid
        )
        return
    if not game.is_started:
        await sio.emit(  # type: ignore
            Emits.ERROR.value,
            GenericErrorResponse(key="ERR_GAME_NOT_STARTED", message="Game has not started"),
            to=sid,
        )
        return

    if game.current_player != sid:
        await sio.emit(  # type: ignore
            Emits.ERROR.value, GenericErrorResponse(key="ERR_NOT_YOUR_TURN", message="It's not your turn"), to=sid
        )
        return
    if game.current_turn != Turn.CHOICE:
        await sio.emit(  # type: ignore
            Emits.ERROR.value,
            GenericErrorResponse(key="ERR_INVALID_STATE", message="It's not your turn to select a piece"),
            to=sid,
        )
        return

    logger.info(f"Player {sid} selected piece {request.piece}")
    try:
        game.choose_piece(request.piece)
    except ValueError as e:
        await sio.emit(  # type: ignore
            Emits.ERROR.value, GenericErrorResponse(key="ERR_INVALID_MOVE", message=str(e)), to=sid
        )
        return

    await emit_game_state_update(game)

    if game.is_pve and game.current_player != sid:
        await game.agent_turn()
        await emit_game_state_update(game)


@sio.on("place-piece")  # type: ignore
async def place_piece(sid: str, request: PlacePieceRequest):
    game = next((game for game in db.list_all().values() if game.id == request.gameId), None)
    if not game or not game.has_player(sid):
        await sio.emit(  # type: ignore
            Emits.ERROR.value, GenericErrorResponse(key="ERR_GAME_NOT_FOUND", message="Game not found"), to=sid
        )
        return
    if not game.is_started:
        await sio.emit(  # type: ignore
            Emits.ERROR.value,
            GenericErrorResponse(key="ERR_GAME_NOT_STARTED", message="Game has not started"),
            to=sid,
        )
        return

    if game.current_player != sid:
        await sio.emit(  # type: ignore
            Emits.ERROR.value, GenericErrorResponse(key="ERR_NOT_YOUR_TURN", message="It's not your turn"), to=sid
        )
        return
    if game.current_turn != Turn.PLACEMENT:
        await sio.emit(  # type: ignore
            Emits.ERROR.value,
            GenericErrorResponse(key="ERR_INVALID_STATE", message="It's not your turn to place a piece"),
            to=sid,
        )
        return

    logger.info(f"Player {sid} placed piece at position {request.cell}")
    try:
        game.place_piece(request.cell)
    except ValueError as e:
        await sio.emit(  # type: ignore
            Emits.ERROR.value, GenericErrorResponse(key="ERR_INVALID_MOVE", message=str(e)), to=sid
        )
        return

    await emit_game_state_update(game)

    if game.is_pve and game.current_player != sid:
        await game.agent_turn()
        await emit_game_state_update(game)


async def emit_game_state_update(game: Game):
    update = GameStateUpdateResponse(
        gameId=game.id,
        currentTurn=game.current_turn.value,
        currentPlayerId=game.current_player,
        currentPiece=game.current_piece.value if game.current_piece is not None else None,
        board=[[piece.value if piece is not None else None for piece in row] for row in game.board],
        availablePieces=[piece.value for piece in game.available_pieces],
        winnerId=game.winner if game.winner is not None else None,
    )

    await sio.emit(Emits.GAME_STATE_UPDATED.value, update, room=game.id)  # type: ignore
