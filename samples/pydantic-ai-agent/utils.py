from typing import Iterable, Literal, assert_never
from pydantic_ai.messages import ModelResponsePart, ModelRequestPart, ModelMessage

from rich.console import Console
from rich.markdown import Markdown

console = Console()


def render_messages(messages: Iterable[ModelMessage]) -> None:
    for message in messages:
        _render_message(message)
    print_markdown("---")


def _render_message(message: ModelMessage) -> None:
    for _type, content in _extract_parts(message.parts):
        if _type == "user":
            print_markdown(f"👤 User:\n{content}")
        else:
            print_markdown(f"🤖 Agent:\n{content}")


# There is probably a better way to do this...
def _extract_parts(
    parts: list[ModelResponsePart] | list[ModelRequestPart],
) -> Iterable[tuple[Literal["user", "agent"], str]]:
    def extract(
        part: ModelResponsePart | ModelRequestPart,
    ) -> Iterable[tuple[Literal["user", "agent"], str]]:
        match part.part_kind:
            case "user-prompt":
                if isinstance(part.content, str):
                    yield "user", part.content
                else:
                    for subpart in part.content:
                        if isinstance(subpart, str):
                            yield "user", subpart
            case "text":
                yield "agent", part.content
            case "tool-call" | "tool-return" | "retry-prompt" | "system-prompt":
                pass
            case _:
                assert_never(part.part_kind)

    for part in parts:
        yield from extract(part)


def print_markdown(markdown: str) -> None:
    console.print(Markdown(markdown))


def ask_prompt() -> str:
    return console.input("[bold magenta]Talk to the SQL agent >> [/]")
