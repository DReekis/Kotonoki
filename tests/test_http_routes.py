import pytest
from app import create_app
from app.config import Config
from app.extensions import db
from app.models import PenName, Branch, Dispatch

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = "test_uploads"
    RATELIMIT_ENABLED = False

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_home_and_static_routes(client):
    res_home = client.get("/")
    assert res_home.status_code == 200
    assert b"All Dispatches" in res_home.data
    assert b"Kotonoki" in res_home.data

    res_about = client.get("/about")
    assert res_about.status_code == 200
    assert b"Our Principles" in res_about.data

    res_rules = client.get("/rules")
    assert res_rules.status_code == 200
    assert b"Rules of Common Ground" in res_rules.data

    res_manifest = client.get("/manifest.json")
    assert res_manifest.status_code == 200
    assert b"Kotonoki" in res_manifest.data

    res_branches = client.get("/branches")
    assert res_branches.status_code == 200
    assert b"Public Branches" in res_branches.data

    res_sw = client.get("/sw.js")
    assert res_sw.status_code == 200
    assert b"kotonoki-v" in res_sw.data

def test_full_auth_and_dispatch_workflow(client):
    # 1. Register new pen name
    res_reg = client.post("/auth/register", data={
        "handle": "forest_monk",
        "password": "Password789!"
    }, follow_redirects=True)
    assert res_reg.status_code == 200
    assert b"forest_monk" in res_reg.data

    # 2. Access /write
    res_write_page = client.get("/write")
    assert res_write_page.status_code == 200
    assert b"Compose Dispatch" in res_write_page.data

    # 3. Publish dispatch
    res_pub = client.post("/write", data={
        "title": "Evening Tea Notes",
        "branch": "tea-ceremony",
        "content_html": "<p>Steeping green tea at sunset.</p>"
    }, follow_redirects=True)
    assert res_pub.status_code == 200
    assert b"Evening Tea Notes" in res_pub.data
    assert b"tea-ceremony" in res_pub.data

    # 4. View in branch feed
    res_branch = client.get("/tea-ceremony")
    assert res_branch.status_code == 200
    assert b"Evening Tea Notes" in res_branch.data

    # 5. Extract dispatch id from database
    with client.application.app_context():
        d = db.session.execute(db.select(Dispatch).where(Dispatch.title == "Evening Tea Notes")).scalar_one()
        d_id = d.id

    # 6. View Sticky Desk memo
    res_sticky = client.get(f"/dispatch/{d_id}/sticky")
    assert res_sticky.status_code == 200
    assert b"Sticky Desk Memo" in res_sticky.data

    # 7. Verify dispatch is judgment-free (no voting buttons or score counters)
    res_detail = client.get(f"/tea-ceremony/{d_id}")
    assert res_detail.status_code == 200
    assert b"vote-btn" not in res_detail.data
    assert b"Upvote" not in res_detail.data

    # 8. Report dispatch
    res_report = client.post(f"/dispatch/{d_id}/report", data={"reason": "Spam"}, headers={"HX-Request": "true"})
    assert res_report.status_code == 200
    assert b"Report submitted" in res_report.data

    # 9. View in My Desk
    res_desk = client.get("/desk")
    assert res_desk.status_code == 200
    assert b"Evening Tea Notes" in res_desk.data

    # 10. Strike (Permanent deletion)
    res_strike = client.post(f"/dispatch/{d_id}/strike", follow_redirects=True)
    assert res_strike.status_code == 200
    assert b"permanently Struck" in res_strike.data

    # 11. Verify dispatch is gone
    res_gone = client.get(f"/tea-ceremony/{d_id}")
    assert res_gone.status_code == 404
