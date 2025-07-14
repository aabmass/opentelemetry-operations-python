# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "langgraph>=0.5.3",
#     "langsmith>=0.4.5",
#     "opentelemetry-api>=1.35.0",
#     "opentelemetry-exporter-otlp-proto-grpc>=1.35.0",
#     "opentelemetry-sdk>=1.35.0",
# ]
#
# ///

# Set up OTel before importing LangChain stuff
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

tracer_provider = TracerProvider()
tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(tracer_provider)


os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_OTEL_ENABLED"] = "true"
os.environ["LANGSMITH_OTEL_ONLY"] = "true"


from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import (
    AIMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent

tracer = trace.get_tracer(__name__)


def get_fake() -> FakeMessagesListChatModel:
    """Returns a fake chat model that does a get_greeting tool call"""

    class FakeModel(FakeMessagesListChatModel):
        def bind_tools(self, *args, **kwargs):
            return self

    return FakeModel(
        responses=[
            AIMessage(
                content="",
                additional_kwargs={
                    "function_call": {"name": "get_greeting", "arguments": "{}"}
                },
                id="run--aee6484e-c974-4e28-8dd0-9038c3bbd303-0",
                tool_calls=[
                    {
                        "name": "get_greeting",
                        "args": {},
                        "id": "02048969-c5ca-4566-b52d-029a6fa37dde",
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content="Hello there 😊",
                name="get_greeting",
                id="177f4a4b-9e1f-4da2-8567-f7d825201241",
                tool_call_id="02048969-c5ca-4566-b52d-029a6fa37dde",
            ),
            AIMessage(
                content="Hello there 😊",
                id="run--a5d90917-ab5b-4e52-95d0-4fe7b79e7021-0",
            ),
        ]
    )


@tool
@tracer.start_as_current_span("hello_from_otel")
def get_greeting() -> str:
    """Get a greeting to give to the user"""
    return "Hello there 😊"


model = get_fake()
checkpointer = InMemorySaver()
agent = create_react_agent(model, tools=[get_greeting])

with tracer.start_as_current_span("otelroot"):
    print(agent.invoke({"messages": ["Send a happy greeting"]})["messages"][-1].content)
