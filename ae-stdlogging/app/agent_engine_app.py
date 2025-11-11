# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# mypy: disable-error-code="attr-defined,arg-type"
import logging
import os
from typing import Any
from unittest.mock import patch

import click
import google.auth
import vertexai
from google.adk.artifacts import GcsArtifactService

# from google.cloud import logging as google_cloud_logging
# from opentelemetry import trace
# from opentelemetry.sdk.trace import TracerProvider, export
from vertexai._genai.types import AgentEngine, AgentEngineConfig
from vertexai.agent_engines.templates.adk import AdkApp
from vertexai import agent_engines
from vertexai._genai.client import Client
from vertexai._genai.agent_engines import AgentEngines

from app.agent import root_agent
from app.utils.deployment import (
    parse_env_vars,
    print_deployment_success,
    write_deployment_metadata,
    asyncio_run,
)
from app.utils.gcs import create_bucket_if_not_exists

# from app.utils.tracing import CloudTraceLoggingSpanExporter
# from app.utils.typing import Feedback


class MyAdkApp(AdkApp):
    def set_up(self) -> None:
        super().set_up()

        import google.auth

        logging.info("Environ before = %s", os.environ)

        # Profiler fails with quota project for some reason. I don't need quota project since I
        # updated to use a service account which is owned by my project
        with patch.dict(os.environ, {"GOOGLE_CLOUD_QUOTA_PROJECT": ""}):
            logging.info("Environ after patch = %s", os.environ)
            try:
                credentials, project_id = google.auth.default()

                logging.info(
                    "Profiler using creds = %s\n%s", credentials, vars(credentials)
                )
                logging.info("Profiler using project_id = %s", project_id)

                if hasattr(credentials, "service_account_email"):
                    service_account_email = credentials.service_account_email
                    logging.info(
                        "The current service account email is: %s",
                        service_account_email,
                    )
                else:
                    logging.warning(
                        "No service account credential found. The application might be using user credentials."
                    )

            except Exception as e:
                print(f"An error occurred: {e}")

            import googlecloudprofiler

            googlecloudprofiler.start(
                service="adk-agent-engine",
                service_version="0.1.0",
                project_id=project_id,
                # verbose is the logging level. 0-error, 1-warning, 2-info,
                # 3-debug. It defaults to 0 (error) if not set.
                verbose=3,
                # project_id must be set if not running on GCP.
                # project_id='my-project-id',
            )


@click.group()
def cli():
    pass


@cli.command()
@click.option(
    "--message",
    # prompt="Enter your message",
    default="What is the weather in San Francisco?",
    help="The message to send to the agent.",
)
@click.option(
    "--agent-name",
    default="ae-stdlogging",
    help="Name of the agent engine to invoke",
)
@click.option(
    "--project",
    default=None,
    help="GCP project ID (defaults to application default credentials)",
)
@click.option(
    "--location",
    default="europe-west3",
    help="GCP region (defaults to europe-west3)",
)
@asyncio_run
async def invoke(message: str, agent_name: str, project: str, location: str):
    """Invokes the deployed agent engine with a message."""
    if not project:
        _, project = google.auth.default()

    vertexai.init(project=project, location=location)
    # client = Client(project=project, location=location)

    # Find the agent by display name
    agent_filter_query = f'display_name="{agent_name}"'
    agent_list = list(agent_engines.list(filter=agent_filter_query))

    if not agent_list:
        logging.error(f"Agent '{agent_name}' not found.")
        return

    agent_engine: AdkApp = agent_list[0]
    # agent_engine: AdkApp = agent_engines.get(matching_agents[0].resource_name)

    logging.info(f"Invoking agent '{agent_name}' with message: '{message}'")
    async for event in agent_engine.async_stream_query(
        message="What is the weather in San Francisco?",
        user_id="123",
        session_id="1324846090528227328",
    ):
        print(f"Agent Response: {event}")


@cli.command()
@click.option(
    "--project",
    default=None,
    help="GCP project ID (defaults to application default credentials)",
)
@click.option(
    "--location",
    default="europe-west3",
    help="GCP region (defaults to europe-west3)",
)
@click.option(
    "--agent-name",
    default="ae-stdlogging",
    help="Name for the agent engine",
)
@click.option(
    "--requirements-file",
    default=".requirements.txt",
    help="Path to requirements.txt file",
)
@click.option(
    "--extra-packages",
    multiple=True,
    default=["./app"],
    help="Additional packages to include",
)
@click.option(
    "--set-env-vars",
    default=None,
    help="Comma-separated list of environment variables in KEY=VALUE format",
)
@click.option(
    "--service-account",
    default="my-ae-serviceaccount@otel-starter-project.iam.gserviceaccount.com",
    help="Service account email to use for the agent engine",
)
@click.option(
    "--staging-bucket-uri",
    default=None,
    help="GCS bucket URI for staging files (defaults to gs://{project}-agent-engine)",
)
@click.option(
    "--artifacts-bucket-name",
    default=None,
    help="GCS bucket name for artifacts (defaults to gs://{project}-agent-engine)",
)
def deploy_agent_engine_app(
    project: str | None,
    location: str,
    agent_name: str,
    requirements_file: str,
    extra_packages: tuple[str, ...],
    set_env_vars: str | None,
    service_account: str | None,
    staging_bucket_uri: str | None,
    artifacts_bucket_name: str | None,
) -> AgentEngine:
    """Deploy the agent engine app to Vertex AI."""

    logging.basicConfig(level=logging.INFO)

    # Parse environment variables if provided
    env_vars = parse_env_vars(set_env_vars)

    if not project:
        _, project = google.auth.default()
    if not staging_bucket_uri:
        staging_bucket_uri = f"gs://{project}-agent-engine"
    if not artifacts_bucket_name:
        artifacts_bucket_name = f"{project}-agent-engine"
    create_bucket_if_not_exists(
        bucket_name=artifacts_bucket_name, project=project, location=location
    )
    create_bucket_if_not_exists(
        bucket_name=staging_bucket_uri, project=project, location=location
    )

    print(
        """
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║   🤖 DEPLOYING AGENT TO VERTEX AI AGENT ENGINE 🤖         ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    )

    extra_packages_list = list(extra_packages)

    # Initialize vertexai client
    agent_engines_client: AgentEngines = Client(
        project=project,
        location=location,
    ).agent_engines
    vertexai.init(project=project, location=location)

    # Read requirements
    with open(requirements_file) as f:
        requirements = f.read().strip().split("\n")
    agent_engine = MyAdkApp(
        agent=root_agent,
        artifact_service_builder=lambda: GcsArtifactService(
            bucket_name=artifacts_bucket_name
        ),
    )
    # Set worker parallelism to 1
    env_vars["NUM_WORKERS"] = "1"
    env_vars["GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"] = "true"
    env_vars["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

    # Common configuration for both create and update operations
    labels: dict[str, str] = {}

    config = AgentEngineConfig(
        display_name=agent_name,
        description="A base ReAct agent built with Google's Agent Development Kit (ADK)",
        extra_packages=extra_packages_list,
        env_vars=env_vars,
        service_account=service_account,
        requirements=requirements,
        staging_bucket=staging_bucket_uri,
        labels=labels,
        gcs_dir_name=agent_name,
        resource_limits={"cpu": "8", "memory": "6Gi"},
        min_instances=2,
        container_concurrency=2,  # defaults to 9
    )

    logging.info(f"Agent config: %s", config)

    # Check if an agent with this name already exists
    existing_agents = list(agent_engines_client.list())
    matching_agents = [
        agent
        for agent in existing_agents
        if agent.api_resource.display_name == agent_name
    ]

    if matching_agents:
        # Update the existing agent with new configuration
        logging.info(f"\n📝 Updating existing agent: {agent_name}")
        remote_agent = agent_engines_client.update(
            name=matching_agents[0].api_resource.name, agent=agent_engine, config=config
        )
    else:
        # Create a new agent if none exists
        logging.info(f"\n🚀 Creating new agent: {agent_name}")
        remote_agent = agent_engines_client.create(agent=agent_engine, config=config)

    write_deployment_metadata(remote_agent)
    print_deployment_success(remote_agent, location, project)

    return remote_agent


if __name__ == "__main__":
    cli()
