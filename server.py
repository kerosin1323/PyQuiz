import datetime
from flask_login import LoginManager, login_user, current_user, logout_user
from flask import Flask, render_template, redirect, request, session
from data import db_session, tests, users
from forms.TestForm import *
from sqlalchemy import desc
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(
    days=365
)
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    """Загрузка пользователя"""
    db_sess = db_session.create_session()
    return db_sess.query(users.User).get(user_id)


@app.route('/', methods=['GET', 'POST'])
def welcome_page():
    """Первая страница"""
    db_sess = db_session.create_session()
    db_sess.query(tests.Tests).filter(tests.Tests.questions == None).delete()
    db_sess.commit()
    amount_tests = len(db_sess.query(tests.Tests).all())
    visitors = len(db_sess.query(users.User).all())
    average = sum(i[0] for i in db_sess.query(users.User.all_right_questions).all()) * 100 // sum(j[0] for j in db_sess.query(users.User.all_questions).all())
    leaders = db_sess.query(users.User).order_by(desc(users.User.marking_test)).all()[:3]
    marking = []
    for i in leaders:
        marking.append(db_sess.query(users.User.marking_test).filter(users.User.id == i.id).first()[0])
    print(marking)
    top_tests = db_sess.query(tests.Tests).order_by(desc(tests.Tests.passing_tests)).all()[:8]
    id_pressed_test = request.form.get('id')
    if id_pressed_test:
        return redirect(f'/tests/{id_pressed_test}/start')
    return render_template('index.html', amount_tests=amount_tests, tests=top_tests,
                           visitors=visitors, leaders=leaders, average=average, marking=marking)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Регистрация пользователя"""
    form = RegisterForm()
    # Проверям нажатие на кнопку залогиниться
    if form.to_login.data:
        return redirect('/login')
    elif form.validate_on_submit():
        db_sess = db_session.create_session()
        # проверяем, есть ли такой пользователь
        if db_sess.query(users.User).filter(users.User.name == form.username.data).first():
            return render_template('register.html',
                                   form=form,
                                   message="Такой пользователь уже есть")
        user = users.User(
            name=form.username.data,
        )
        user.set_password(form.password.data)
        db_sess.add(user)
        db_sess.commit()
        login_user(user)
        return redirect('/')
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Авторизация пользователя"""
    form = LoginForm()
    if form.register.data:
        return redirect('/register')
    elif form.validate_on_submit():
        db_sess = db_session.create_session()
        user = db_sess.query(users.User).filter(users.User.name == form.username.data).first()
        # проверка пароля и тогоб есть ли такой пользователь
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect("/")
        return render_template('login.html',
                               message="Неправильный логин или пароль",
                               form=form)
    return render_template('login.html', title='Авторизация', form=form, current_user=current_user)


@app.route('/choose_category', methods=['GET', 'POST'])
def choose_category():
    """Вывод категорий"""
    form = CategoryForm()
    if form.validate_on_submit():
        pressed = [i for i, k in form.data.items() if k][0]
        return redirect(f'/tests/{pressed}')
    return render_template('category.html', form=form, current_user=current_user)


@app.route('/tests/<category>', methods=['GET', 'POST'])
def show_all_tests(category):
    """ВЫвод всех тестов выбранной категории"""
    print(category)
    trans_dict = {'films': 'Фильмы', 'sport': 'Спорт', 'foods': 'еда', 'games': 'Игры', 'science': 'Наука',
                  'tech': 'Технологии', 'others': 'Другое', 'music': 'Музыка'}
    db_sess = db_session.create_session()
    test = db_sess.query(tests.Tests).filter(tests.Tests.category == trans_dict[category]).all()
    if not test:
        return 'Тестов с такой категорией пока нет'
    if request.method == 'POST' and test:
        test_id = request.form.get('id')
        return redirect(f'/tests/{test_id}/start')
    return render_template('all_tests.html', tests=test, current_user=current_user, title=f'Тесты по категории {trans_dict[category].lower()}')


@app.route('/tests/<test_id>/start', methods=['GET', 'POST'])
def start_test(test_id):
    """Первое окно теста"""
    db_sess = db_session.create_session()
    test = db_sess.query(tests.Tests).filter(tests.Tests.id == test_id).first()
    user = db_sess.query(users.User).filter(users.User.id == test.user_id).first()
    user_pressed = request.form.get('user')
    to_start = request.form.get('start')
    to_delete = request.form.get('delete')
    to_change = request.form.get('change')
    if request.method == 'POST' and to_start:
        return redirect(f'/take_test/{test_id}/1')
    elif user_pressed:
        return redirect(f'/profile/{user.id}')
    elif to_delete:
        db_sess.query(tests.Tests).filter(tests.Tests.id == test_id).delete()
        db_sess.commit()
        return redirect('/')
    elif to_change:
        return redirect(f'/change_test/{test_id}')
    return render_template('start_test.html', test=test, mark=test.mark, current_user=current_user, user=user)


@app.route('/take_test/<test_id>/<question>', methods=['GET', 'POST'])
def take_test(test_id, question):
    """Процесс прохождения теста"""
    try:
        number_trying = list(session.get(str(test_id), {}).keys())[-1]
    except IndexError:
        number_trying = str(0)
    if question == '1' and request.method == 'GET':
        number_trying = str(int(number_trying) + 1)
    mark = session.get(str(test_id), {}).get(number_trying, {}).get('mark', 0)
    right_answers = session.get(str(test_id), {}).get(number_trying, {}).get('right_answers', 0)
    session[str(test_id)] = {**session.get(str(test_id), {}), number_trying: {"mark": mark, 'right_answers': right_answers}}
    db_sess = db_session.create_session()
    test = db_sess.query(tests.Tests).filter(tests.Tests.id == test_id).first()
    # загружаем данные в виде json
    data = json.loads(test.questions)
    if request.method == 'POST' and int(question) <= len(data):
        # проверяем на правильность ответ пользователя
        if [j for j, v in data[question]['answers'].items()][int(request.form.get('index'))] == [i for i, k in data[question]['answers'].items() if k][0]:
            session[str(test_id)][number_trying]['right_answers'] = right_answers + 1
        return redirect(f'/take_test/{test_id}/{int(question) + 1}')
    # обрабатываем данные оценки
    if request.form.get('mark') == '+' and mark < 1:
        session[str(test_id)][number_trying]['mark'] += 1
        mark += 1
    elif request.form.get('mark') == '-' and mark > -1:
        session[str(test_id)][number_trying]['mark'] -= 1
        mark -= 1
    if int(question) <= len(data):
        return render_template('questions.html', number_question=question, name=data[question]['name'], answer=[i for i in data[question]['answers']], current_user=current_user)
    # обработка кнопки выхода
    if request.form.get('exit') == '1':
        if number_trying == '1':
            test.mark += mark
        else:
            test.mark -= session[str(test_id)][str(int(number_trying) - 1)]['mark']
            test.mark += mark
        if number_trying == '1':
            user = db_sess.query(users.User).filter(users.User.id == current_user.id).first()
            user.all_questions += len(data)
            user.all_right_questions += session[str(test_id)][number_trying]['right_answers']
            user.passed_tests += 1
        session[str(test_id)][number_trying]['right_answers'] = 0
        db_sess.commit()
        return redirect('/')
    return render_template('finish_test.html', right_answers=right_answers, all_questions=len(data), percent=int(right_answers/len(data)*100), mark=f'+{mark}' if mark == 1 else mark, current_user=current_user)


@app.route('/make_test', methods=['GET', 'POST'])
def make_test():
    """Процесс создания теста"""
    form = MakingTestForm()
    if form.validate_on_submit():
        test = tests.Tests()
        test.name = form.name.data
        test.category = form.category.data
        test.describe = form.describe.data
        test.user_id = current_user.id
        test.created_date = datetime.date.today()
        db_sess = db_session.create_session()
        db_sess.add(test)
        db_sess.commit()
        return redirect(f'/create_question/{test.id}/1')
    return render_template('make_test.html', title='Создание теста', form=form, current_user=current_user)


@app.route('/change_test/<test_id>', methods=['GET', 'POST'])
def change_test(test_id):
    form = ChangingTestForm()
    db_sess = db_session.create_session()
    test = db_sess.query(tests.Tests).filter(tests.Tests.id == test_id).first()
    if form.validate_on_submit():
        test.name = form.name.data
        test.category = form.category.data
        test.describe = form.describe.data
        test.created_date = datetime.date.today()
        db_sess.commit()
        return redirect(f'/change_question/{test.id}/1')
    else:
        form.name.data = test.name
        form.category.data = test.category
        form.describe.data = test.describe
    return render_template('make_test.html', title='Изменение теста', form=form, current_user=current_user)


@app.route('/change_question/<test_id>/<number>', methods=['GET', 'POST'])
def change_questions(test_id, number):
    db_sess = db_session.create_session()
    test = db_sess.query(tests.Tests).filter(tests.Tests.id == test_id).first()
    form = ChangingQuestion()
    data = json.loads(test.questions)
    if request.form.get('delete-question'):
        del data[str(number)]
        test.questions = json.dumps(data)
        db_sess.commit()
        return redirect(f'/change_question/{test_id}/{int(number) + 1}')
    elif form.validate_on_submit():
        checks = (form.check_right1.data, form.check_right2.data, form.check_right3.data, form.check_right4.data)
        variants = (form.answer1.data, form.answer2.data, form.answer3.data, form.answer4.data)
        # проверка: правильный ответ должен быть одним
        if sum(1 for i in checks if i) > 1:
            return render_template('make_question.html', form=form, number=number, current_user=current_user,
                                   message='Правильный ответ должен быть одним!')
        elif not sum(1 for i in checks if i):
            return render_template('make_question.html', form=form, number=number, current_user=current_user,
                                   message='Выберите верный вариант ответа!')
        # Преобразуем данные вопроса в json
        questions_str = {f'{number}': {'name': form.question.data,
                                       'answers': {variants[0]: checks[0],
                                                   variants[1]: checks[1],
                                                   variants[2]: checks[2],
                                                   variants[3]: checks[3]}}}
        try:
            prev_questions = json.loads(test.questions)
        except TypeError:
            prev_questions = {}
        # и в строку, для хранения в БД

        test.questions = json.dumps({**prev_questions, **questions_str}, ensure_ascii=False)
        db_sess.commit()
        if form.add_question.data:
            return redirect(f'/change_question/{test_id}/{int(number) + 1}')
        elif form.create.data:
            result = {}
            for i in range(1, len(data) + 1):
                result[str(i)] = list(data.items())[i - 1][1]
            test.questions = json.dumps(result, ensure_ascii=False)
            db_sess.commit()
            return redirect('/')
    else:
        form.question.data = data[str(number)]['name']
        answers = [i for i, k in data[str(number)]['answers'].items()]
        checks = [k for i, k in data[str(number)]['answers'].items()]
        form.answer1.data = answers[0]
        form.answer2.data = answers[1]
        form.answer3.data = answers[2]
        form.answer4.data = answers[3]
        form.check_right1.data = checks[0]
        form.check_right2.data = checks[1]
        form.check_right3.data = checks[2]
        form.check_right4.data = checks[3]
    return render_template('make_question.html', form=form, number=number, current_user=current_user, able_to_delete=True)


@app.route('/create_question/<test_id>/<number>', methods=['GET', "POST"])
def create_question(number, test_id):
    """Процесс создания вопросов"""
    db_sess = db_session.create_session()
    test = db_sess.query(tests.Tests).filter(tests.Tests.id == test_id).first()
    form = MakingQuestion()
    if form.validate_on_submit():
        # обрабатываем данные: получаем все варианты ответов и их правильность
        checks = (form.check_right1.data, form.check_right2.data, form.check_right3.data, form.check_right4.data)
        variants = (form.answer1.data, form.answer2.data, form.answer3.data, form.answer4.data)
        # проверка: правильный ответ должен быть одним
        if sum(1 for i in checks if i) > 1:
            return render_template('make_question.html', form=form, number=number, current_user=current_user, message='Правильный ответ должен быть одним!')
        elif not sum(1 for i in checks if i):
            return render_template('make_question.html', form=form, number=number, current_user=current_user, message='Выберите верный вариант ответа!')
        # Преобразуем данные вопроса в json
        questions_str = {f'{number}': {'name': form.question.data,
                                                  'answers': {variants[0]: checks[0],
                                                              variants[1]: checks[1],
                                                              variants[2]: checks[2],
                                                              variants[3]: checks[3]}}}
        try:
            prev_questions = json.loads(test.questions)
        except TypeError:
            prev_questions = {}
        # и в строку, для хранения в БД
        test.questions = json.dumps({**prev_questions, **questions_str}, ensure_ascii=False)
        db_sess.commit()
        if form.add_question.data:
            return redirect(f'/create_question/{test_id}/{int(number) + 1}')
        elif form.create.data:
            return redirect('/')
    return render_template('make_question.html', form=form, number=number, current_user=current_user, able_to_delete=False)


@app.route('/profile', methods=['GET', 'POST'])
def open_profile():
    """Вывод данных о пользователе"""
    form = ProfileView()
    db_sess = db_session.create_session()
    user = db_sess.query(users.User).filter(users.User.id == current_user.id).first()
    percent = 0
    if user.all_questions:
        percent = user.all_right_questions / user.all_questions * 100
    if form.created_tests.data:
        return redirect(f'/created_tests')
    if form.exit.data:
        logout_user()
        return redirect('/')
    return render_template('profile_check.html', name=current_user.name, checked_tests_count=int(user.passed_tests), percent=int(percent), form=form, current_user=current_user, mark=user.marking_test)


@app.route('/profile/<user_id>', methods=['GET', 'POST'])
def profile_user(user_id):
    form = ProfileView()
    db_sess = db_session.create_session()
    user = db_sess.query(users.User).filter(users.User.id == user_id).first()
    percent = 0
    if user.all_questions:
        percent = user.all_right_questions / user.all_questions * 100
    if form.created_tests.data:
        return redirect(f'/created_tests')
    if form.exit.data:
        logout_user()
        return redirect('/')
    return render_template('profile_check.html', name=user.name, checked_tests_count=int(user.passed_tests),
                           percent=int(percent), form=form, current_user=current_user, mark=user.marking_test)


@app.route('/created_tests', methods=['GET', 'POST'])
def show_created_tests():
    """Показать все тесты, которые создал пользователь"""
    db_sess = db_session.create_session()
    test = db_sess.query(tests.Tests).filter(tests.Tests.user_id == current_user.id).all()
    if request.method == 'POST':
        test_id = request.form.get('id')
        return redirect(f'/tests/{test_id}/start')
    if not test:
        return 'Пользователь не создал ни одного теста'
    return render_template('all_tests.html', tests=test, current_user=current_user, title=f'Тесты пользователя {current_user.name}')


def main():
    db_session.global_init("db/blogs.db")
    app.run()


if __name__ == '__main__':
    main()
