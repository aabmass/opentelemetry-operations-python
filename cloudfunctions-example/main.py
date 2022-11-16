from opentelemetry.sdk.resources import Resource
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from opentelemetry.context import get_current
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.cloud_trace_propagator import (
    CloudTraceFormatPropagator,
)
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.instrumentation.wsgi import OpenTelemetryMiddleware
import flask

print(f"Startup app is {flask.current_app=}")
flask.current_app.wsgi_app = OpenTelemetryMiddleware(flask.current_app.wsgi_app)

set_global_textmap(CloudTraceFormatPropagator())
tracer_provider = TracerProvider(
    sampler=TraceIdRatioBased(1),
    resource=Resource.create(
        {
            "service.name": "flask-on-cloud-functions",
            "service.environment": "myenviron",
        }
    ),
)
# exporter = ConsoleSpanExporter()
exporter = CloudTraceSpanExporter(resource_regex="service.*")
tracer_provider.add_span_processor(
    SimpleSpanProcessor(exporter)
)
trace.set_tracer_provider(tracer_provider)

def hello_world(request):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.
    """
    print(f"Current context: {get_current()}")
    return f'Hello World!'
