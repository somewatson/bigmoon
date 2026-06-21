import pytest
from app.main import app as flask_app
from app.models import db, User, Favorite, DownloadTask
from flask_login import login_user

@pytest.fixture
def app():
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "test-key"
    })
    with flask_app.app_context():
        db.create_all()
        # Create a test admin
        admin = User(username="testadmin", role="admin")
        admin.set_password("testpass")
        db.session.add(admin)
        db.session.commit()
        return flask_app

@pytest.fixture
def client(app):
    return app.test_client()

def test_login_success(client, app):
    response = client.post('/login', data={'username': 'testadmin', 'password': 'testpass'})
    assert response.status_code == 302
    assert '/ ' in response.location

def test_login_failure(client, app):
    response = client.post('/login', data={'username': 'wrong', 'password': 'wrong'})
    assert response.status_code == 200 # Returns login page

def test_admin_access_restricted(client, app):
    # Try to access admin without login
    response = client.get('/admin')
    assert response.status_code == 302 # Redirect to login

def test_favorites_api(client, app):
    # Login first
    client.post('/login', data={'username': 'testadmin', 'password': 'testpass'})
    
    # Add favorite
    resp = client.post('/api/favorites', 
                       json={'channel': 'shroud'}, 
                       content_type='application/json')
    assert resp.status_code == 200
    assert resp.json['status'] == 'added'
    
    # Verify favorite exists
    resp = client.get('/api/favorites')
    assert 'shroud' in resp.json['favorites']
    
    # Remove favorite
    resp = client.post('/api/favorites', 
                       json={'channel': 'shroud'}, 
                       content_type='application/json')
    assert resp.json['status'] == 'removed'
    
    resp = client.get('/api/favorites')
    assert 'shroud' not in resp.json['favorites']

def test_task_creation(client, app):
    client.post('/login', data={'username': 'testadmin', 'password': 'testpass'})
    
    resp = client.post('/api/download', 
                       json={'url': 'http://twitch.tv/video/123', 'id': '123'}, 
                       content_type='application/json')
    assert resp.status_code == 200
    assert 'taskId' in resp.json
    
    # Check if task is in DB
    with app.app_context():
        task = DownloadTask.query.get(resp.json['taskId'])
        assert task is not None
        assert task.status == 'pending'

def test_clear_failed_tasks(client, app):
    client.post('/login', data={'username': 'testadmin', 'password': 'testpass'})
    
    # Create a failed task
    with app.app_context():
        failed_task = DownloadTask(video_id="fail1", status="error", filename="fail.mp4")
        db.session.add(failed_task)
        db.session.commit()
        task_id = failed_task.id
    
    # Clear failed tasks
    resp = client.post('/api/tasks/clear_failed')
    assert resp.status_code == 200
    
    # Verify it's gone
    with app.app_context():
        task = DownloadTask.query.get(task_id)
        assert task is None
