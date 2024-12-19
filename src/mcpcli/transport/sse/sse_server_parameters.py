from dataclasses import dataclass
from typing import Optional

@dataclass
class SSEServerParameters:
    """SSE Server Parameters"""
    endpoint: str = "http://localhost:8000/sse"
   
    
    @property
    def url(self) -> str:
        """Return server URL"""
        return self.endpoint