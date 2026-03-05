from pydantic import BaseModel, Field
from typing import Literal, Optional
import time


class UserInput(BaseModel):
    type: Literal["text", "select", "number", "all_digits", "calendar"] = "text"
    text: Optional[str] = None
    number: Optional[str] = None
    select: Optional[int] = None
    date: Optional[str] = None


class UIOutput(BaseModel):
    text: Optional[str] = None
    answer_type: Literal["text", "select", "number", "calendar"] = "text"
    select_options: Optional[list[str]] = None
    initial_date: Optional[str] = None
    allow_free_text: bool = True


class AgentResp(BaseModel):
    ui_output: Optional[UIOutput] = None
    control_status: Literal["keep", "release"] = "keep"
    other_data: dict[str, str] = Field(default_factory=dict)
    suggested_agent: Optional[str] = None


class AgentRequest(BaseModel):
    conversation_id: str
    user_input: UserInput
    other_data: dict[str, str] = Field(default_factory=dict)


class Turn(BaseModel):
    role: Literal["user", "bot"]
    obj: UserInput | UIOutput | None = None


class Log(BaseModel):
    level: str
    message: str
    timestamp: float = Field(default_factory=lambda: time.time())
