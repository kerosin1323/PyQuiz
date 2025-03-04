from typing import Type
from data import users, articles, db_session, comments
from sqlalchemy import desc, and_
from flask import *
import json
import datetime
from werkzeug.utils import secure_filename
import os
from forms.ArticleForm import *
from forms.UserForm import *
from flask_login import *
from data.users import Users


class Article:
    def __init__(self):
        self.db_sess = db_session.create_session()

    def create(self, text: str, form: CreatingArticleDataForm, user_id: Users.id, app: Flask) -> None:
        text = text.replace('<img', '<img height="100%" width="100%"')
        article = articles.Articles(text=text, user_id=user_id, created_date=datetime.datetime.now(),
                                    brand=form.brand_category.data, body=form.body_category.data,
                                    motors=form.motors_category.data, price_from=form.price_from.data,
                                    price_to=form.price_to.data, name=form.name.data, describe=form.describe.data,
                                    categories=form.category.data)
        file = form.photo.data
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            article.photo = filename
        self.db_sess.add(article)
        self.db_sess.commit()

    def getArticlesOnCategory(self, category: str = None) -> list:
        if category is None:
            return self.db_sess.query(articles.Articles).filter(
                articles.Articles.created_date.ilike('%' + f'{datetime.datetime.today().date()}' + '%')).order_by(
                desc(articles.Articles.readings)).all()
        elif category == 'subscribed' and current_user.is_authenticated:
            self.getArticlesFromSubscribedUsers(current_user)
        elif category != 'subscribed':
            categories = {'tops': 'Топ', 'reviews': 'Обзоры', 'comparisons': 'Сравнения'}
            return self.db_sess.query(articles.Articles).filter(and_(
                articles.Articles.created_date.ilike('%' + str(datetime.datetime.today().date()) + '%'),
                articles.Articles.categories == categories[category])).order_by(
                desc(articles.Articles.readings)).all()
        return []

    def getArticlesFromSubscribedUsers(self, user: Users) -> list:
        all_subs = [int(i) for i, k in json.loads(user.subscribed).items() if k == '1']
        return self.db_sess.query(articles.Articles).filter(and_(
            articles.Articles.created_date.ilike('%' + str(datetime.datetime.today().date()) + '%'),
            articles.Articles.user_id.in_(all_subs))).order_by(
            desc(articles.Articles.readings)).all()

    def getArticlesFromUser(self, user_id: Users.id) -> list:
        return self.db_sess.query(articles.Articles).filter(articles.Articles.user_id == user_id).all()

    def getDataArticles(self, all_articles: list) -> dict:
        data = {}
        for article in all_articles:
            creator = self.db_sess.query(users.Users).filter(users.Users.id == article.user_id).first()
            time = text_delta(datetime.datetime.now() - article.created_date)
            data[str(article.id)] = (creator.name, creator.photo, creator.subscribers, time, len(
                Comment().getCommentFromArticle(article.id)))
        return data

    def toRead(self) -> str | None:
        to_read = request.form.get('read')
        if to_read:
            self._read(to_read)
            return to_read

    def delete(self):
        to_delete = request.form.get('delete')
        if to_delete:
            self.db_sess.query(articles.Articles).filter(articles.Articles.id == to_delete).delete()
            self.db_sess.commit()

    def _read(self, id_article: articles.Articles.id) -> None:
        article = self.getArticleOnID(id_article)
        article.readings += 1
        user = self.db_sess.query(users.Users).filter(users.Users.id == article.user_id).first()
        user.reading += 1
        self.db_sess.commit()

    def findOnText(self, text: str) -> list:
        return self.db_sess.query(articles.Articles).filter(articles.Articles.name.ilike('%' + text + '%')).order_by(
            desc(articles.Articles.readings)).all()

    def getArticleOnID(self, article_id: articles.Articles.id) -> Type[articles.Articles]:
        return self.db_sess.query(articles.Articles).filter(articles.Articles.id == article_id).first()

    def addMark(self, article_id: articles.Articles.id, mark: int) -> None:
        article = self.getArticleOnID(article_id)
        user = self.db_sess.query(Users).filter(Users.id == current_user.id).first()
        author = User().getUserOnID(article.user_id)
        prev_mark = json.loads(user.marked_articles)
        if (not prev_mark) or (not str(article_id) in prev_mark.keys()):
            article.mark += mark
            author.mark += mark
            prev_mark[str(article_id)] = str(mark)
        elif 1 >= int(prev_mark[str(article_id)]) + mark >= -1:
            article.mark += (mark - int(prev_mark[str(article_id)]))
            author.mark += (mark - int(prev_mark[str(article_id)]))
            prev_mark[str(article_id)] = str(mark)
        elif not 1 >= int(prev_mark[str(article_id)]) + mark >= -1:
            article.mark -= mark
            author.mark -= mark
            prev_mark[str(article_id)] = '0'
        user.marked_articles = json.dumps(prev_mark)
        self.db_sess.commit()

    def getFollowedArticles(self, user_id: Users.id) -> list:
        user = User().getUserOnID(user_id)
        return [self.getArticleOnID(int(i)) for i, k in json.loads(user.marked_articles).items() if k == '1']


def text_delta(t: datetime) -> str:
    if t < datetime.timedelta(minutes=1):
        return "Минуту назад"
    elif t < datetime.timedelta(hours=1):
        return f"{t.total_seconds() // 60:.0f} минут назад"
    elif t < datetime.timedelta(days=1):
        return f"{t.total_seconds() // 3600:.0f} часов назад"
    elif t < datetime.timedelta(days=30):
        return f"{t.days} дней назад"
    elif t < datetime.timedelta(days=365):
        return f"{t.days // 30} месяцев назад"
    else:
        return f"{t.days // 365} лет назад"


class User:
    def __init__(self):
        self.db_sess = db_session.create_session()

    def create(self, form: RegisterForm) -> None:
        user = Users(name=form.username.data, login=form.login.data)
        user.set_password(form.password.data)
        self.db_sess.add(user)
        self.db_sess.commit()
        login_user(user)

    def addUserData(self, form: DescriptionProfile, user_id: Users.id, app: Flask) -> None:
        user = self.getUserOnID(user_id)
        user.name = form.name.data
        photo = form.photo.data
        if photo:
            filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            user.photo = filename
        user.description = form.description.data
        user.contacts = form.contacts.data
        self.db_sess.commit()

    def getUserOnID(self, user_id: Users.id) -> Type[Users]:
        return self.db_sess.query(Users).filter(Users.id == user_id).first()

    def userAlreadyExist(self, login: str) -> bool:
        return bool(len(self.db_sess.query(Users).filter(Users.login == login).all()))

    def checkAndLogin(self, name: str, password: str) -> Response:
        user = self.db_sess.query(Users).filter(Users.name == name).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect("/")

    def getMRSLeaders(self) -> dict:
        mark_leaders = self.db_sess.query(Users).order_by(desc(Users.mark))[:5]
        reading_leaders = self.db_sess.query(Users).order_by(desc(Users.reading))[:5]
        subscribers_leaders = self.db_sess.query(Users).order_by(desc(Users.subscribers))[:5]
        return {'mark': mark_leaders, 'reading': reading_leaders, 'subscribe': subscribers_leaders}

    def getSubscriptions(self, user_id: Users.id) -> list:
        user = self.getUserOnID(user_id)
        if user.subscribed:
            return [self.getUserOnID(int(i)) for i, k in json.loads(user.subscribed).items() if k == '1']

    def subscribeOn(self, user_id: Users.id) -> None:
        user = self.getUserOnID(current_user.id)
        author = self.getUserOnID(user_id)
        prev_subs = json.loads(user.subscribed)
        if (not prev_subs) or (str(user_id) not in prev_subs) or (prev_subs[str(user_id)] == '0'):
            author.subscribers += 1
            prev_subs[str(user_id)] = '1'
        elif prev_subs[str(user_id)] == '1':
            author.subscribers -= 1
            prev_subs[str(user_id)] = '0'
        user.subscribed = json.dumps(prev_subs)
        self.db_sess.commit()

    def checkSubscribe(self, user_id: Users.id) -> bool:
        user = self.getUserOnID(current_user.id)
        if user.subscribed:
            return str(user_id) in [str(i) for i, k in json.loads(user.subscribed).items() if k == '1']


class Comment:
    def __init__(self):
        self.db_sess = db_session.create_session()

    def getCommentFromArticle(self, article_id: articles.Articles.id) -> list:
        return self.db_sess.query(comments.Comments).filter(comments.Comments.article_id == article_id).all()

    def getCommentsData(self, all_comments: list) -> dict:
        data = {}
        for comment in all_comments:
            creator = self.db_sess.query(users.Users).filter(users.Users.id == comment.user_id).first()
            time = text_delta(datetime.datetime.now() - comment.created_date)
            data[str(comment.id)] = (creator.name, creator.photo, creator.subscribers, time)
        return data

    def addMark(self, comment_id: comments.Comments.id, mark: int) -> None:
        comment = self.db_sess.query(comments.Comments).filter(comments.Comments.id == comment_id).first()
        if f'{current_user.id}' not in session or 'comments' not in session[str(current_user.id)] or str(
                comment_id) not in session[f'{current_user.id}']['comments']:
            comment.mark += mark
            session[f'{current_user.id}'] = {'comments': {f'{comment_id}': mark}}
        elif 1 >= int(session[f'{current_user.id}']['comments'][str(comment_id)]) + int(mark) >= -1:
            comment.mark += int(mark)
            comment.mark -= int(session[f'{current_user.id}']['comments'][str(comment_id)])
            session[f'{current_user.id}'] = {'comments': {f'{comment_id}': mark}}
        elif int(session[f'{current_user.id}']['comments'][str(comment_id)]) + int(mark) <= -1 or int(
                session[f'{current_user.id}']['comments'][str(comment_id)]) + int(mark) >= 1:
            comment.mark -= int(mark)
            session[f'{current_user.id}'] = {'comments': {f'{comment_id}': '0'}}
        self.db_sess.commit()

    def create(self, text: str, article_id: articles.Articles.id, answer_on: str) -> None:
        comment = comments.Comments(user_id=current_user.id, text=text, article_id=article_id,
                          created_date=datetime.datetime.now(), answer_on=answer_on)
        self.db_sess.add(comment)
        self.db_sess.commit()

    def getAllAnswers(self, all_comments: list[comments.Comments]) -> dict[comments.Comments.id: comments.Comments]:
        answers = {}
        for comment in all_comments:
            answers[str(comment.id)] = self.db_sess.query(comments.Comments).filter(comments.Comments.answer_on == comment.id).all()
        return answers
