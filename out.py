# import logging
# import sys

# # from google.cloud.logging_v2.handlers import StructuredLogHandler
# from opentelemetry.exporter.cloud_logging import CloudLoggingExporter
# from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler, LogRecord
# from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor

# # Set up OTel logging pipeline
# logger_provider = LoggerProvider()
# exporter = CloudLoggingExporter(structured_json_file=sys.stdout)
# logger_provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
# otel_handler = LoggingHandler(logger_provider=logger_provider)


# logging.basicConfig(
#     level=logging.INFO,
#     handlers=[
#         # StructuredLogHandler(),
#         otel_handler,
#     ],
# )

# logger_provider.get_logger(__name__).emit(
#     record=LogRecord(
#         attributes={"hello": "world"}, body={"foo": {"bar": "baz"}}
#     )
# )


# logging.info("Hello here is a message", extra={"foo": "bar"})

import json
import sys
import timeit
from opentelemetry.exporter.cloud_logging import (
    CloudLoggingExporter,
)
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor

logger_provider = LoggerProvider()
set_logger_provider(logger_provider)
exporter = CloudLoggingExporter(structured_json_file=sys.stdout)
logger_provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))


otel_logger = logger_provider.get_logger(__name__)


def emit_log():
    otel_logger.emit(
        attributes={"hello": "world"}, body={"foo": {"bar": "baz"}}
    )


def print_log_directly():
    print(
        json.dumps(
            dict(attributes={"hello": "world"}, body={"foo": {"bar": "baz"}})
        )
    )


number_of_runs = 1000

for func, name in ((emit_log, "emit"), (print_log_directly, "print")):
    print(f"Timing {name}...")
    total_time = timeit.timeit(func, number=number_of_runs)
    print(f"Execution summary for {name}() over {number_of_runs} runs:")
    print(f"  Total time: {total_time:.4f} seconds")
    print(f"  Average time per run: {total_time / number_of_runs:.6f} seconds")
    print("-" * 30)
