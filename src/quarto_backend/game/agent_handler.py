import httpx
from quarto_lib import AgentHealthResponse, ChooseInitialPieceResponse, CompleteTurnResponse, GameState


class AgentHandler:
    def __init__(self, endpoint: str) -> None:
        self._endpoint = endpoint
        self._identifier: str | None = None

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @property
    def identifier(self) -> str:
        if self._identifier is None:
            raise RuntimeError("Agent identifier is not set. Ensure initialize() has been called.")
        return self._identifier

    async def initialize(self) -> "AgentHandler":
        await self.check_health()
        return self

    async def check_health(self) -> None:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.endpoint}/")
                response.raise_for_status()
                health_data = AgentHealthResponse.model_validate(response.json())
                self._identifier = health_data.identifier
        except httpx.RequestError as e:
            raise RuntimeError(f"Failed to connect to agent at {self.endpoint}: {e}")
        except ValueError as e:
            raise RuntimeError(f"Invalid response format from agent at {self.endpoint}: {e}")

    async def choose_initial_piece(self) -> ChooseInitialPieceResponse:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{self.endpoint}/choose-initial-piece", timeout=10)
                response.raise_for_status()
                return ChooseInitialPieceResponse.model_validate(response.json())
        except httpx.RequestError as e:
            raise RuntimeError(f"Failed to connect to agent at {self.endpoint}: {e}")
        except ValueError as e:
            raise RuntimeError(f"Invalid response format from agent at {self.endpoint}: {e}")

    async def complete_turn(self, game: GameState) -> CompleteTurnResponse:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{self.endpoint}/complete-turn", json=game.model_dump(), timeout=10)
                response.raise_for_status()
                return CompleteTurnResponse.model_validate(response.json())
        except httpx.RequestError as e:
            raise RuntimeError(f"Failed to connect to agent at {self.endpoint}: {e}")
        except ValueError as e:
            raise RuntimeError(f"Invalid response format from agent at {self.endpoint}: {e}")
