import datetime
import sqlalchemy
from sqlalchemy import orm
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .db_session import SqlAlchemyBase


class User(SqlAlchemyBase, UserMixin):
    __tablename__ = 'users'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    hashed_password = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    all_right_questions = sqlalchemy.Column(sqlalchemy.Integer, default=0)
    all_questions = sqlalchemy.Column(sqlalchemy.Integer, default=0)
    passed_tests = sqlalchemy.Column(sqlalchemy.Integer, default=0)
    marking_test = sqlalchemy.Column(sqlalchemy.Integer, default=0)
    tests = orm.relationship("Tests", back_populates='user')

    def set_password(self, password):
        self.hashed_password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.hashed_password, password)
