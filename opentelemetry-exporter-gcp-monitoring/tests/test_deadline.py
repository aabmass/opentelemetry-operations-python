# Copyright 2022 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from unittest.mock import patch, Mock
from opentelemetry.exporter.cloud_monitoring._deadline import Deadline
from pytest import approx


@patch("opentelemetry.exporter.cloud_monitoring._deadline.time")
def test_deadline(time_mock: Mock) -> None:
    time_mock.return_value = 0.0

    # 5 seconds in future
    deadline = Deadline(5000.0)
    assert deadline.timeout_seconds() == approx(5.0)

    # advance time 0.5 seconds
    time_mock.return_value = 0.5
    assert deadline.timeout_seconds() == approx(4.5)

    # advance time to deadline at 5 seconds
    time_mock.return_value = 5.0
    assert deadline.timeout_seconds() == approx(0)

    # past deadline, expect a negative timeout
    time_mock.return_value = 6.0
    assert deadline.timeout_seconds() < 0
