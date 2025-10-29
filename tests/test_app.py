import unittest
from app import app, db, EmailRecord


class BasicTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        # Use in-memory SQLite for isolated testing
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()
        with app.app_context():
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_home_page_loads(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)

    def test_email_record_model(self):
        with app.app_context():
            record = EmailRecord(
                email='test@example.com',
                subject='Test',
                body='Hello'
            )
            db.session.add(record)
            db.session.commit()
            saved = EmailRecord.query.first()
            self.assertEqual(saved.email, 'test@example.com')


if __name__ == "__main__":
    unittest.main()
