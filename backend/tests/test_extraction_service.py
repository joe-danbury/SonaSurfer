import sys
from pathlib import Path

# Ensure backend root is on the Python path in CI/pytest environments.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.extraction_service import ExtractionService


class _FakeTextBlock:
    def __init__(self, text: str):
        self.text = text


class _FakeResponse:
    def __init__(self, text: str):
        self.content = [_FakeTextBlock(text)]


class _FakeMessages:
    def __init__(self, text: str):
        self._text = text

    def create(self, **kwargs):
        return _FakeResponse(self._text)


class _FakeClient:
    def __init__(self, text: str):
        self.messages = _FakeMessages(text)


def _service_with_fake_client(response_text: str) -> ExtractionService:
    service = ExtractionService.__new__(ExtractionService)
    service.client = _FakeClient(response_text)
    service.model = "test-model"
    service.system_prompt = "test-prompt"
    return service


def test_extract_songs_parses_json_code_block():
    service = _service_with_fake_client(
        '```json\n[{"track":"Dreams","artist":"Fleetwood Mac"}]\n```'
    )

    songs = service.extract_songs("recommend me classic songs")

    assert songs == [{"track": "Dreams", "artist": "Fleetwood Mac"}]


def test_extract_songs_returns_empty_list_on_invalid_json():
    service = _service_with_fake_client("not-json")

    songs = service.extract_songs("anything")

    assert songs == []


def test_extract_new_songs_incremental_filters_existing():
    service = ExtractionService.__new__(ExtractionService)
    service.extract_songs = lambda _: [
        {"track": "Dreams", "artist": "Fleetwood Mac"},
        {"track": "Time", "artist": "Pink Floyd"},
    ]
    already_extracted = {("dreams", "fleetwood mac")}

    new_songs = service.extract_new_songs_incremental("unused", already_extracted)

    assert new_songs == [{"track": "Time", "artist": "Pink Floyd"}]
