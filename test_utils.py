import os
import io
from unittest.mock import patch

from google_classroom_client import GoogleClassroomClient
from googleapiclient.http import HttpMockSequence


def _read_http_fixture(response_json_path):
    abs_path = os.path.join(os.path.dirname(__file__), response_json_path)
    if os.path.exists(abs_path):
        return io.open(abs_path, "r", encoding='utf8').read()
    else:
        return response_json_path


def patch_google_api_http(*response_json_paths):
    http = HttpMockSequence(
        [({'status': 200}, _read_http_fixture(path)) for path in response_json_paths]
    )
    return patch.object(GoogleClassroomClient, 'http', http)


def patch_failed_api_http(error_json_path, status=400):
    failed_response = ({'status': status}, _read_http_fixture(error_json_path))
    http = HttpMockSequence(
        [
            # First call is always a discovery, patch it.
            ({'status': 200}, _read_http_fixture('data/discovery.json')),
            # Ignore failed API retries
            *[failed_response] * 3,
            # Subsequent call is made to a specific service after all retries failed.
            # That's the one we are interested in.
            failed_response,
        ]
    )
    return patch.object(GoogleClassroomClient, 'http', http)