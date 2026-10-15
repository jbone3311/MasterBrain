"""First-party XLSX review assets are served without exposing a worker route."""

from fastapi.testclient import TestClient
from test_service import registry

from email_brain.api import create_app
from email_brain.store import Store


def test_first_party_xlsx_review_asset_is_fixed_and_no_store() -> None:
    app = create_app(Store("dbname=email_brain_test_xlsx_static"), registry())
    with TestClient(app) as client:
        page = client.get("/")
        script = client.get("/xlsx_review.js")
        assert page.status_code == script.status_code == 200
        assert 'src="/xlsx_review.js"' in page.text
        assert 'id="xlsx-review-approve"' in page.text
        assert script.headers["cache-control"] == "no-store"
        assert "email-xlsx-results" in script.text
        assert "publish-reviewed-xlsx" not in script.text
        forbidden = "/v1/brain/email-xlsx-results/xapp_" + "a" * 32 + "/publish"
        assert client.post(forbidden).status_code == 404
