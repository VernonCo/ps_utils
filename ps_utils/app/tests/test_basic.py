
import os, unittest2, sys
sys.path.append(os.path.dirname(os.getcwd()))

from app import app, basedir, db   # , mail


TEST_DB = 'test.db'


class BasicTests(unittest2.TestCase):

    ############################
    #### setup and teardown ####
    ############################

    # executed prior to each test
    def setUp(self):
        app.config['TESTING'] = True  # Disables sending emails during unit testing
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['DEBUG'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + \
            os.path.join(basedir, TEST_DB)
        app.config['SECRET_KEY'] = "asdljfsvu80q2tr4t/lm3wqgevbiu3qnt03i]t-gpfdvjm"
        self.app = app.test_client()
        db.drop_all()
        db.create_all()

    # executed after each test
    def tearDown(self):
        pass


###############
#### tests ####
###############

    def test_main_page(self):
        response = self.app.get('/', follow_redirects=True)
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    # unittest.main()
    import nose2
    nose2.main()
