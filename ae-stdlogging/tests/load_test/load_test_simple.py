from opentelemetry import trace
import httpx
import os
import json
import logging
import asyncio


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# Load testing parameters
CONCURRENT_REQUESTS = 10
TIME_LIMIT = 60

# Initialize Vertex AI and load agent config
with open("deployment_metadata.json") as f:
    remote_agent_engine_id = json.load(f)["remote_agent_engine_id"]

parts = remote_agent_engine_id.split("/")
project_id = parts[1]
location = parts[3]
engine_id = parts[5]

# Convert remote agent engine ID to streaming URL.
url = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/reasoningEngines/{engine_id}:streamQuery"

logger.info("Using remote agent engine ID: %s", remote_agent_engine_id)
logger.info("Using URL: %s", url)

headers = {"Content-Type": "application/json"}
headers["Authorization"] = f"Bearer {os.environ['_AUTH_TOKEN']}"

data = {
    "class_method": "async_stream_query",
    "input": {
        "user_id": "test",
        "message": "What's the weather in San Francisco?",
    },
}


async def make_request(client: httpx.AsyncClient):
    with tracer.start_as_current_span("loadtest-simple") as span:
        logger.info(
            "trace ID = %s", trace.format_trace_id(span.get_span_context().trace_id)
        )
        # async with client.stream(
        #     "POST", url, headers=headers, json=data, params={"alt": "sse"}
        # ) as response:
        #     async for line in response.aiter_lines():
        #         logger.info("Got line %s", line)
        response = await client.post(url, headers=headers, json=data)
        async for line in response.aiter_lines():
            logger.info("Got line %s", line)

    logger.info("Done with request")


async def main():
    async with asyncio.timeout(TIME_LIMIT):
        # catch timeout and exit gracefully
        try:
            async with (
                httpx.AsyncClient(timeout=20) as client,
                asyncio.TaskGroup() as tg,
            ):
                for _ in range(CONCURRENT_REQUESTS):
                    tg.create_task(make_request(client))
        except asyncio.TimeoutError:
            logger.info("Timeout reached. Exiting gracefully.")
            return


if __name__ == "__main__":
    asyncio.run(main())
