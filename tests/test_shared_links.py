import unittest
from app.main import app as flask_app
from app.models import db, DownloadTask, SharedLink
from datetime import datetime, timedelta
import secrets

class TestSharedLinks(unittest.TestCase):
    def setUp(self):
        flask_app.config['TESTING'] = True
        flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = flask_app.test_client()
        with flask_app.app_context():
            # Force recreate all tables in memory
            db.drop_all()
            db.create_all()
            # Create a dummy user
            from app.models import User
            user = User(username='testuser', password_hash='hash', role='admin')
            db.session.add(user)
            db.session.commit()
            
            # Create a dummy task
            task = DownloadTask(user_id=user.id, filename='test_video.mp4', status='completed')
            db.session.add(task)
            db.session.commit()
            self.task = task
            self.user = user

    def tearDown(self):
        with flask_app.app_context():
            db.session.remove()
            db.drop_all()

    def test_generate_share_link(self):
        with self.client.session_transaction() as sess:
            from flask_login import login_user
            login_user(self.user)
        
        response = self.client.post('/api/library/share', 
                                 json={'filename': 'test_video.mp4'})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('url', data)
        self.assertIn('expires_at', data)
        
        token = data['url'].split('/')[-1]
        with flask_app.app_context():
            shared_link = SharedLink.query.filter_by(token=token).first()
            self.assertIsNotNone(shared_link)
            self.assertEqual(shared_link.task_id, self.task.id)

    def test_share_download_valid(self):
        with flask_app.app_context():
            token = secrets.token_urlsafe(32)
            shared_link = SharedLink(
                task_id=self.task.id,
                token=token,
                expires_at=datetime.utcnow() + timedelta(hours=1)
            )
            db.session.add(shared_link)
            db.session.commit()
        
        # We can't actually check send_from_directory without a real file on disk in memory db
        # but we can check that it doesn't return 404 or 410
        response = self.client.get(f'/share/{token}')
        # Since the file doesn't exist on disk, it should return "File not found on disk" 404
        # as per the implementation: if not os.path.exists... return 404
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"File not found on disk", response.data)

    def test_share_download_expired(self):
        with flask_app.app_context():
            token = secrets.token_urlsafe(32)
            shared_link = SharedLink(
                task_id=self.task.id,
                token=token,
                expires_at=datetime.utcnow() - timedelta(hours=1)
            )
            db.session.add(shared_link)
            db.session.commit()
        
        response = self.client.get(f'/share/{token}')
        self.assertEqual(response.status_code, 410)
        self.assertIn(b"Link expired", response.data)

    def test_share_download_invalid_token(self):
        response = self.client.get('/share/nonexistenttoken')
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"Link not found", response.data)

if __name__ == '__main__':
    unittest.main()
