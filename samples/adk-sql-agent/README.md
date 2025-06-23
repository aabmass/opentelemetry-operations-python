# OpenTelemetry ADK instrumentation example

<!-- TODO: link to devsite doc once it is published -->

This sample is an ADK agent instrumented with OpenTelemetry to send traces and logs with GenAI
prompts and responses, and metrics to Google Cloud Observability.

The Agent is a SQL expert that has full access to an ephemeral SQLite database. The database is
initially empty.

## APIs and Permissions

Enable the relevant Cloud Observability APIs if they aren't already enabled.
```sh
gcloud services enable telemetry.googleapis.com logging.googleapis.com monitoring.googleapis.com cloudtrace.googleapis.com
```

This sample writes to Cloud Logging, Cloud Monitoring, and Cloud Trace. Grant yourself the
following roles to run the example:
- `roles/logging.logWriter` – see https://cloud.google.com/logging/docs/access-control#permissions_and_roles
- `roles/monitoring.metricWriter` – see https://cloud.google.com/monitoring/access-control#predefined_roles
- `roles/telemetry.writer` – see https://cloud.google.com/trace/docs/iam#telemetry-roles

## Running the example

The sample can easily be run in Cloud Shell. You can also use
[Application Default Credentials][ADC] locally. Clone:
```sh
git clone https://github.com/GoogleCloudPlatform/opentelemetry-operations-python.git
cd opentelemetry-operations-python/samples/adk-sql-agent
```

<!-- 
# Capture GenAI prompts and responses
export OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true
# Capture application logs automatically
export OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true
```

Create a virtual environment and run the sample:
```sh
python -m venv venv/
source venv/bin/activate
pip install -r requirements.txt
python main.py
``` -->

Update the `GOOGLE_CLOUD_PROJECT` environment variable in [`main.env`](./main.env) or set it in your shell.

Use [`uv`](https://docs.astral.sh/uv/) to run:

```sh
uv run --env-file main.env main.py
```

## Note on Semantic Conventions

This sample uses
[opentelemetry-instrumentation-google-genai](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation-genai/opentelemetry-instrumentation-google-genai)
to get spans following OpenTelemetry semantic conventions for inference calls to VertexAI. This
powers Cloud Trace's GenAI experience. ADK emits it's own `call_llm` spans which do not
currently follow OpenTelemetry semantic conventions
https://github.com/google/adk-python/issues/356.

## Viewing the results

To view the generated traces with [Generative AI
events](https://cloud.google.com/trace/docs/finding-traces#view_generative_ai_events) in the
GCP console, use the [Trace Explorer](https://cloud.google.com/trace/docs/finding-traces). Filter for spans named `invoke agent`.

[ADC]: https://cloud.google.com/docs/authentication/application-default-credentials
