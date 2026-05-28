import os
import json
import io
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

from flask import Flask, render_template, redirect, url_for, flash, request, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, PasswordField, SubmitField, SelectField, HiddenField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from flask_bcrypt import Bcrypt

try:
    from flask_socketio import SocketIO, emit, join_room
except ImportError:
    SocketIO = None
    emit = None
    join_room = None

load_dotenv()

app = Flask(__name__)
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PROFILE_UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads', 'profiles')
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024
app.config['ENABLE_SOCKETIO'] = os.environ.get('ENABLE_SOCKETIO', '').lower() in {'1', 'true', 'yes'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
bcrypt = Bcrypt(app)
csrf = CSRFProtect(app)
socketio_options = {'cors_allowed_origins': '*'}
socketio_async_mode = os.environ.get('SOCKETIO_ASYNC_MODE')
if socketio_async_mode:
    socketio_options['async_mode'] = socketio_async_mode
socketio = SocketIO(app, **socketio_options) if SocketIO and app.config['ENABLE_SOCKETIO'] else None

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, teacher, student, parent
    account_id = db.Column(db.Integer, unique=True, nullable=True)  # 6-digit code starting at 250000
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    @staticmethod
    def next_account_id():
        last = User.query.filter(User.account_id.isnot(None)).order_by(User.account_id.desc()).first()
        if last and last.account_id and last.account_id >= 250000:
            return last.account_id + 1
        return 250000

@login_manager.user_loader
def load_user(user_id):
    user = db.session.get(User, int(user_id))
    if user and user.is_active:
        return user
    return None

class RegisterForm(FlaskForm):
    username = StringField('Tên đăng nhập', validators=[DataRequired(), Length(3,80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Mật khẩu', validators=[DataRequired(), Length(6,128)])
    password2 = PasswordField('Xác nhận mật khẩu', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Vai trò', choices=[('student','Học sinh'),('parent','Phụ huynh')], validators=[DataRequired()])
    submit = SubmitField('Đăng ký')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Mật khẩu', validators=[DataRequired()])
    role = HiddenField('role')
    submit = SubmitField('Đăng nhập')

class CreateTeacherForm(FlaskForm):
    username = StringField('Tên đăng nhập', validators=[DataRequired(), Length(3,80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Mật khẩu', validators=[DataRequired(), Length(6,128)])
    password2 = PasswordField('Xác nhận mật khẩu', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Tạo tài khoản giáo viên')

class ChangePasswordForm(FlaskForm):
    password = PasswordField('Mật khẩu mới', validators=[DataRequired(), Length(6,128)])
    password2 = PasswordField('Xác nhận mật khẩu', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Cập nhật mật khẩu')

class MessageForm(FlaskForm):
    content = TextAreaField('Nội dung', validators=[DataRequired(), Length(1,1000)])
    submit = SubmitField('Gửi')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reply_to = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=True)


class PsychologyTopic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PsychologyQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('psychology_topic.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(255), nullable=False)
    option_b = db.Column(db.String(255), nullable=False)
    option_c = db.Column(db.String(255), nullable=False)
    option_d = db.Column(db.String(255), nullable=False)
    position = db.Column(db.Integer, default=0)


class PsychologySubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('psychology_topic.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    percent = db.Column(db.Integer, nullable=False)
    level = db.Column(db.Integer, nullable=False)
    answers_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatConversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_type = db.Column(db.String(20), nullable=False)  # kbot, teacher
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('chat_conversation.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    sender_role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class EmotionEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mood = db.Column(db.String(40), nullable=False)
    intensity = db.Column(db.Integer, nullable=False)
    triggers_json = db.Column(db.Text, nullable=False)
    note = db.Column(db.Text, nullable=True)
    prompt = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StudentProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    full_name = db.Column(db.String(160), nullable=True)
    class_name = db.Column(db.String(80), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(40), nullable=True)
    guardian_name = db.Column(db.String(160), nullable=True)
    guardian_phone = db.Column(db.String(40), nullable=True)
    emergency_contact = db.Column(db.String(160), nullable=True)
    avatar_filename = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_complete(self):
        required_fields = [self.full_name, self.class_name, self.address, self.phone, self.guardian_name, self.guardian_phone]
        return all(value and value.strip() for value in required_fields)


class TeacherProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    full_name = db.Column(db.String(160), nullable=True)
    department = db.Column(db.String(120), nullable=True)
    subject = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(40), nullable=True)
    email_contact = db.Column(db.String(120), nullable=True)
    office_location = db.Column(db.String(160), nullable=True)
    consultation_time = db.Column(db.String(160), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    avatar_filename = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_complete(self):
        required_fields = [self.full_name, self.department, self.subject, self.phone, self.email_contact]
        return all(value and value.strip() for value in required_fields)


class CareerTest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CareerQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('career_test.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    option_a = db.Column(db.String(255), nullable=False)
    option_b = db.Column(db.String(255), nullable=False)
    option_c = db.Column(db.String(255), nullable=False)
    option_d = db.Column(db.String(255), nullable=False)
    position = db.Column(db.Integer, default=0)


class CareerSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('career_test.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    percent = db.Column(db.Integer, nullable=False)
    answers_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CareerJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    field = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(40), nullable=True)
    summary = db.Column(db.String(255), nullable=False)
    skills_json = db.Column(db.Text, nullable=False)
    work = db.Column(db.Text, nullable=False)
    study = db.Column(db.String(80), nullable=False)
    salary = db.Column(db.String(80), nullable=False)
    demand = db.Column(db.String(80), nullable=False)
    personality = db.Column(db.Text, nullable=False)
    color = db.Column(db.String(40), default='purple')
    is_featured = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CareerInquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('career_job.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question = db.Column(db.Text, nullable=False)
    reply = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    replied_at = db.Column(db.DateTime, nullable=True)


class CareerLearningPath(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    summary = db.Column(db.String(255), nullable=False)
    icon = db.Column(db.String(40), nullable=True)
    color = db.Column(db.String(40), default='purple')
    goal_label = db.Column(db.String(160), nullable=True)
    completion_percent = db.Column(db.Integer, default=0)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CareerPathStage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    path_id = db.Column(db.Integer, db.ForeignKey('career_learning_path.id'), nullable=False)
    year_label = db.Column(db.String(80), nullable=False)
    subtitle = db.Column(db.String(120), nullable=True)
    title = db.Column(db.String(160), nullable=False)
    status = db.Column(db.String(40), nullable=False)
    is_open = db.Column(db.Boolean, default=True)
    position = db.Column(db.Integer, default=0)


class CareerPathTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stage_id = db.Column(db.Integer, db.ForeignKey('career_path_stage.id'), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    subtitle = db.Column(db.String(180), nullable=True)
    task_type = db.Column(db.String(40), nullable=False)
    is_done = db.Column(db.Boolean, default=False)
    position = db.Column(db.Integer, default=0)


class CareerPathSkill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    path_id = db.Column(db.Integer, db.ForeignKey('career_learning_path.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    level_label = db.Column(db.String(80), nullable=False)
    percent = db.Column(db.Integer, default=0)
    color = db.Column(db.String(40), default='purple')


class ForumPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ForumReaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reaction_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ForumComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ForumReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class LifeSkillLesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    skill_category = db.Column(db.String(80), nullable=False)
    video_url = db.Column(db.String(500), nullable=False)
    thumbnail_url = db.Column(db.String(500), nullable=True)
    duration = db.Column(db.String(40), nullable=True)
    description = db.Column(db.Text, nullable=False)
    practice_steps = db.Column(db.Text, nullable=True)
    reflection_question = db.Column(db.String(255), nullable=True)
    is_featured = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LifeSkillProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('life_skill_lesson.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    feedback = db.Column(db.String(80), nullable=True)
    reflection = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def psychology_rating(percent):
    if percent <= 20:
        return {
            'level': 1,
            'title': 'Bình thường',
            'range': 'Điểm 0–20',
            'description': 'Cảm xúc ổn định, không có dấu hiệu bất thường',
            'badge': 'Ổn định',
            'class': 'level-1',
        }
    if percent <= 40:
        return {
            'level': 2,
            'title': 'Chú ý nhẹ',
            'range': 'Điểm 21–40',
            'description': 'Có một số lo lắng hoặc căng thẳng nhất thời',
            'badge': 'Theo dõi',
            'class': 'level-2',
        }
    if percent <= 60:
        return {
            'level': 3,
            'title': 'Cần hỗ trợ',
            'range': 'Điểm 41–60',
            'description': 'Lo âu hoặc buồn bã đáng kể, ảnh hưởng sinh hoạt',
            'badge': 'Hỗ trợ',
            'class': 'level-3',
        }
    if percent <= 80:
        return {
            'level': 4,
            'title': 'Nghiêm trọng',
            'range': 'Điểm 61–80',
            'description': 'Dấu hiệu trầm cảm hoặc lo âu nặng, cần can thiệp',
            'badge': 'Can thiệp',
            'class': 'level-4',
        }
    return {
        'level': 5,
        'title': 'Khủng hoảng',
        'range': 'Điểm 81–100',
        'description': 'Có biểu hiện tự hại hoặc nguy hiểm tức thời',
        'badge': 'Khẩn cấp',
        'class': 'level-5',
    }


def all_psychology_ratings():
    return [psychology_rating(score) for score in (20, 40, 60, 80, 100)]


def role_required(*roles):
    if current_user.role not in roles:
        flash('Bạn không có quyền truy cập chức năng này', 'danger')
        return False
    return True


def allowed_profile_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'webp'}


def save_profile_image(file_storage, user_id, prefix='student'):
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_profile_image(file_storage.filename):
        return None
    os.makedirs(app.config['PROFILE_UPLOAD_FOLDER'], exist_ok=True)
    extension = secure_filename(file_storage.filename).rsplit('.', 1)[1].lower()
    filename = f'{prefix}-{user_id}-{int(datetime.utcnow().timestamp())}.{extension}'
    file_storage.save(os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], filename))
    return filename


def video_embed_url(video_url):
    url = (video_url or '').strip()
    if 'youtube.com/watch' in url and 'v=' in url:
        video_id = url.split('v=', 1)[1].split('&', 1)[0]
        return f'https://www.youtube.com/embed/{video_id}'
    if 'youtu.be/' in url:
        video_id = url.rsplit('/', 1)[1].split('?', 1)[0]
        return f'https://www.youtube.com/embed/{video_id}'
    if 'youtube.com/shorts/' in url:
        video_id = url.split('/shorts/', 1)[1].split('?', 1)[0]
        return f'https://www.youtube.com/embed/{video_id}'
    return ''


def video_platform(video_url):
    url = (video_url or '').lower()
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'YouTube'
    if 'tiktok.com' in url:
        return 'TikTok'
    return 'Video'


def collect_life_skill_lesson_form():
    return {
        'title': (request.form.get('title') or '').strip(),
        'skill_category': (request.form.get('skill_category') or '').strip(),
        'video_url': (request.form.get('video_url') or '').strip(),
        'thumbnail_url': (request.form.get('thumbnail_url') or '').strip(),
        'duration': (request.form.get('duration') or '').strip(),
        'description': (request.form.get('description') or '').strip(),
        'practice_steps': (request.form.get('practice_steps') or '').strip(),
        'reflection_question': (request.form.get('reflection_question') or '').strip(),
        'is_featured': request.form.get('is_featured') == 'on',
        'is_published': request.form.get('is_published') == 'on',
    }


def topic_question_count(topic_id):
    return PsychologyQuestion.query.filter_by(topic_id=topic_id).count()


def collect_quiz_questions():
    question_texts = request.form.getlist('question_text[]')
    option_as = request.form.getlist('option_a[]')
    option_bs = request.form.getlist('option_b[]')
    option_cs = request.form.getlist('option_c[]')
    option_ds = request.form.getlist('option_d[]')
    questions = []
    for index, text in enumerate(question_texts):
        values = {
            'question_text': text.strip(),
            'option_a': option_as[index].strip() if index < len(option_as) else '',
            'option_b': option_bs[index].strip() if index < len(option_bs) else '',
            'option_c': option_cs[index].strip() if index < len(option_cs) else '',
            'option_d': option_ds[index].strip() if index < len(option_ds) else '',
        }
        if any(values.values()):
            if not all(values.values()):
                return None
            values['position'] = len(questions) + 1
            questions.append(values)
    return questions


def collect_career_questions():
    question_texts = request.form.getlist('question_text[]')
    image_urls = request.form.getlist('image_url[]')
    option_as = request.form.getlist('option_a[]')
    option_bs = request.form.getlist('option_b[]')
    option_cs = request.form.getlist('option_c[]')
    option_ds = request.form.getlist('option_d[]')
    questions = []
    for index, text in enumerate(question_texts):
        values = {
            'question_text': text.strip(),
            'image_url': image_urls[index].strip() if index < len(image_urls) else '',
            'option_a': option_as[index].strip() if index < len(option_as) else '',
            'option_b': option_bs[index].strip() if index < len(option_bs) else '',
            'option_c': option_cs[index].strip() if index < len(option_cs) else '',
            'option_d': option_ds[index].strip() if index < len(option_ds) else '',
        }
        required_values = [values['question_text'], values['option_a'], values['option_b'], values['option_c'], values['option_d']]
        if any(required_values) or values['image_url']:
            if not all(required_values):
                return None
            values['position'] = len(questions) + 1
            questions.append(values)
    return questions


def career_question_count(test_id):
    return CareerQuestion.query.filter_by(test_id=test_id).count()


def career_job_to_dict(job):
    try:
        skills = json.loads(job.skills_json or '[]')
    except json.JSONDecodeError:
        skills = []
    return {
        'id': job.id,
        'teacher_id': job.teacher_id,
        'name': job.name,
        'field': job.field,
        'icon': job.icon or '◇',
        'summary': job.summary,
        'skills': skills,
        'work': job.work,
        'study': job.study,
        'salary': job.salary,
        'demand': job.demand,
        'personality': job.personality,
        'color': job.color or 'purple',
        'featured': bool(job.is_featured),
    }


def career_library_data():
    jobs = CareerJob.query.filter_by(is_published=True).order_by(CareerJob.is_featured.desc(), CareerJob.updated_at.desc()).all()
    return [career_job_to_dict(job) for job in jobs]


def collect_career_job_form():
    skills = [
        item.strip()
        for item in (request.form.get('skills') or '').split(',')
        if item.strip()
    ]
    return {
        'name': (request.form.get('name') or '').strip(),
        'field': (request.form.get('field') or '').strip(),
        'icon': (request.form.get('icon') or '').strip(),
        'summary': (request.form.get('summary') or '').strip(),
        'skills': skills,
        'work': (request.form.get('work') or '').strip(),
        'study': (request.form.get('study') or '').strip(),
        'salary': (request.form.get('salary') or '').strip(),
        'demand': (request.form.get('demand') or '').strip(),
        'personality': (request.form.get('personality') or '').strip(),
        'color': (request.form.get('color') or 'purple').strip(),
        'is_featured': request.form.get('is_featured') == 'on',
    }


def default_learning_path_payload(title='Lập trình viên'):
    stages = [
        {
            'year_label': 'Lớp 10',
            'subtitle': '',
            'title': 'Xây nền tảng',
            'status': 'Chưa hoàn thành',
            'is_open': True,
            'tasks': [
                {'title': 'Học tốt Toán, Vật lý, Tin học', 'subtitle': 'Môn học nền tảng cho lập trình', 'type': 'Môn học', 'done': False},
                {'title': 'Làm quen với tư duy logic', 'subtitle': 'Giải bài tập thuật toán cơ bản', 'type': 'Kỹ năng', 'done': False},
                {'title': 'Thử viết chương trình đơn giản', 'subtitle': 'Python hoặc Scratch', 'type': 'Thực hành', 'done': False},
            ],
        },
        {
            'year_label': 'Lớp 11',
            'subtitle': 'Đang học',
            'title': 'Phát triển kỹ năng',
            'status': 'Đang làm',
            'is_open': True,
            'tasks': [
                {'title': 'Học Python cơ bản đến nâng cao', 'subtitle': 'Biến, vòng lặp, hàm, OOP', 'type': 'Kỹ năng', 'done': False},
                {'title': 'Duy trì điểm Toán trên 8.0', 'subtitle': 'Nền tảng cho CNTT đại học', 'type': 'Môn học', 'done': False},
                {'title': 'Làm 1 dự án nhỏ hoàn chỉnh', 'subtitle': 'Web đơn giản hoặc app console', 'type': 'Thực hành', 'done': False},
                {'title': 'Tham gia câu lạc bộ Tin học', 'subtitle': 'Trải nghiệm làm việc nhóm', 'type': 'Hoạt động', 'done': False},
            ],
        },
        {
            'year_label': 'Lớp 12',
            'subtitle': '',
            'title': 'Chuẩn bị thi & hồ sơ',
            'status': 'Sắp tới',
            'is_open': False,
            'tasks': [
                {'title': 'Chọn tổ hợp xét tuyển phù hợp', 'subtitle': 'CNTT, khoa học máy tính, kỹ thuật phần mềm', 'type': 'Môn học', 'done': False},
                {'title': 'Hoàn thiện portfolio dự án', 'subtitle': 'Lưu lại sản phẩm đã làm', 'type': 'Thực hành', 'done': False},
            ],
        },
        {
            'year_label': 'Đại học',
            'subtitle': '',
            'title': 'Chuyên sâu & thực tập',
            'status': 'Tương lai',
            'is_open': False,
            'tasks': [
                {'title': 'Học cấu trúc dữ liệu và thuật toán', 'subtitle': 'Nền tảng đi làm lâu dài', 'type': 'Kỹ năng', 'done': False},
                {'title': 'Tìm thực tập năm 3', 'subtitle': 'Làm quen môi trường công ty', 'type': 'Hoạt động', 'done': False},
            ],
        },
    ]
    skills = [
        {'name': 'Lập trình Python', 'level': 'Trung cấp', 'percent': 60, 'color': 'purple'},
        {'name': 'Toán tư duy', 'level': 'Khá tốt', 'percent': 75, 'color': 'green'},
        {'name': 'Tiếng Anh', 'level': 'Cơ bản', 'percent': 45, 'color': 'yellow'},
        {'name': 'Làm việc nhóm', 'level': 'Đang rèn', 'percent': 40, 'color': 'pink'},
    ]
    return json.dumps(stages, ensure_ascii=False, indent=2), json.dumps(skills, ensure_ascii=False, indent=2)


def parse_learning_path_payload(stages_text, skills_text):
    try:
        stages = json.loads(stages_text or '[]')
        skills = json.loads(skills_text or '[]')
    except json.JSONDecodeError:
        return None, None
    if not isinstance(stages, list) or not isinstance(skills, list):
        return None, None
    return stages, skills


def replace_learning_path_details(path, stages, skills):
    stage_ids = [stage.id for stage in CareerPathStage.query.filter_by(path_id=path.id).all()]
    if stage_ids:
        CareerPathTask.query.filter(CareerPathTask.stage_id.in_(stage_ids)).delete(synchronize_session=False)
    CareerPathStage.query.filter_by(path_id=path.id).delete()
    CareerPathSkill.query.filter_by(path_id=path.id).delete()
    for stage_index, stage_data in enumerate(stages, start=1):
        stage = CareerPathStage(
            path_id=path.id,
            year_label=(stage_data.get('year_label') or f'Giai đoạn {stage_index}').strip(),
            subtitle=(stage_data.get('subtitle') or '').strip(),
            title=(stage_data.get('title') or 'Mục tiêu giai đoạn').strip(),
            status=(stage_data.get('status') or 'Sắp tới').strip(),
            is_open=bool(stage_data.get('is_open', True)),
            position=stage_index,
        )
        db.session.add(stage)
        db.session.flush()
        for task_index, task_data in enumerate(stage_data.get('tasks') or [], start=1):
            db.session.add(CareerPathTask(
                stage_id=stage.id,
                title=(task_data.get('title') or 'Nhiệm vụ').strip(),
                subtitle=(task_data.get('subtitle') or '').strip(),
                task_type=(task_data.get('type') or 'Kỹ năng').strip(),
                is_done=bool(task_data.get('done')),
                position=task_index,
            ))
    for skill_data in skills:
        db.session.add(CareerPathSkill(
            path_id=path.id,
            name=(skill_data.get('name') or 'Kỹ năng').strip(),
            level_label=(skill_data.get('level') or 'Đang rèn').strip(),
            percent=int(skill_data.get('percent') or 0),
            color=(skill_data.get('color') or 'purple').strip(),
        ))


def learning_path_details(path_id):
    stages = CareerPathStage.query.filter_by(path_id=path_id).order_by(CareerPathStage.position, CareerPathStage.id).all()
    stage_ids = [stage.id for stage in stages]
    tasks_by_stage = defaultdict(list)
    if stage_ids:
        tasks = CareerPathTask.query.filter(CareerPathTask.stage_id.in_(stage_ids)).order_by(CareerPathTask.position, CareerPathTask.id).all()
        for task in tasks:
            tasks_by_stage[task.stage_id].append(task)
    skills = CareerPathSkill.query.filter_by(path_id=path_id).order_by(CareerPathSkill.id).all()
    total_tasks = sum(len(tasks_by_stage.get(stage.id, [])) for stage in stages)
    done_tasks = sum(1 for stage in stages for task in tasks_by_stage.get(stage.id, []) if task.is_done)
    return stages, tasks_by_stage, skills, total_tasks, done_tasks


def career_insights(student_id):
    entries = EmotionEntry.query.filter_by(student_id=student_id).order_by(EmotionEntry.created_at.desc()).limit(30).all()
    result = []
    evening_stress = sum(1 for entry in entries if entry.mood in ('cang_thang', 'lo_lang') and entry.created_at and entry.created_at.hour >= 18)
    friend_tags = 0
    study_tags = 0
    for entry in entries:
        try:
            triggers = json.loads(entry.triggers_json or '[]')
        except json.JSONDecodeError:
            triggers = []
        friend_tags += sum(1 for trigger in triggers if 'bạn' in trigger.lower())
        study_tags += sum(1 for trigger in triggers if 'học' in trigger.lower())
    if evening_stress:
        result.append({
            'icon': '☾',
            'title': 'Cảm xúc thường xuống vào buổi tối',
            'body': f'Có {evening_stress} lần căng thẳng/lo lắng sau 18:00 gần đây — có thể liên quan đến lịch học hoặc nghỉ ngơi.',
            'badge': 'Mới phát hiện',
            'tone': 'purple',
        })
    if friend_tags:
        result.append({
            'icon': '♧',
            'title': 'Bạn bè là nguồn vui lớn nhất',
            'body': f'Có {friend_tags} lần nhật ký nhắc đến bạn bè — bạn lấy năng lượng tốt từ kết nối xã hội.',
            'badge': 'Đã xác nhận',
            'tone': 'green',
        })
    if study_tags:
        result.append({
            'icon': '▤',
            'title': 'Áp lực học tập tăng trước kỳ kiểm tra',
            'body': f'Có {study_tags} ghi chú liên quan học tập — nên theo dõi lịch ôn bài và thời gian nghỉ.',
            'badge': 'Đang theo dõi',
            'tone': 'orange',
        })
    if not result:
        result = [
            {
                'icon': '☾',
                'title': 'Bắt đầu ghi nhật ký để thấy pattern rõ hơn',
                'body': 'Sau vài ngày check-in, hệ thống sẽ phát hiện cảm xúc hay xuất hiện theo thời gian và nguyên nhân cụ thể.',
                'badge': 'Mới phát hiện',
                'tone': 'purple',
            },
            {
                'icon': '♧',
                'title': 'Bài khám phá sẽ giúp hiểu phong cách học',
                'body': 'Làm 1–2 bài ngắn để hệ thống ghép dữ liệu nhật ký với sở thích và điểm mạnh của bạn.',
                'badge': 'Đang theo dõi',
                'tone': 'green',
            },
        ]
    return result[:3]


def career_emotion_trends(student_id):
    entries = EmotionEntry.query.filter_by(student_id=student_id).order_by(EmotionEntry.created_at.desc()).limit(30).all()
    total = len(entries) or 1
    excited = sum(1 for entry in entries if entry.mood == 'vui')
    stress = sum(1 for entry in entries if entry.mood in ('cang_thang', 'lo_lang'))
    calm = sum(1 for entry in entries if entry.mood in ('binh_than', 'buon'))
    return [
        {'label': 'Vui / Phấn khích', 'percent': round(excited / total * 100), 'color': '#8b7ce8'},
        {'label': 'Căng thẳng / Lo lắng', 'percent': round(stress / total * 100), 'color': '#e56b3f'},
        {'label': 'Bình thản / Trung lập', 'percent': round(calm / total * 100), 'color': '#3aa77b'},
    ]


def career_personality_summary(student_id):
    submission_count = CareerSubmission.query.filter_by(student_id=student_id).count()
    entries = EmotionEntry.query.filter_by(student_id=student_id).order_by(EmotionEntry.created_at.desc()).limit(20).all()
    friend_tags = 0
    study_tags = 0
    for entry in entries:
        try:
            triggers = json.loads(entry.triggers_json or '[]')
        except json.JSONDecodeError:
            triggers = []
        friend_tags += sum(1 for trigger in triggers if 'bạn' in trigger.lower())
        study_tags += sum(1 for trigger in triggers if 'học' in trigger.lower())
    if friend_tags >= study_tags and friend_tags:
        return {
            'title': 'Người kết nối tinh tế',
            'body': 'Bạn nhạy với cảm xúc xung quanh và thường nạp năng lượng từ các mối quan hệ tích cực.',
        }
    if submission_count:
        return {
            'title': 'Người quan sát nhạy cảm',
            'body': 'Bạn chú ý đến cảm xúc của mình và có xu hướng suy nghĩ kỹ trước khi hành động.',
        }
    return {
        'title': 'Người đang khám phá',
        'body': 'Hãy làm vài bài khám phá và ghi nhật ký để hệ thống gọi tên điểm mạnh nổi bật của bạn rõ hơn.',
    }


def conversation_room(conversation_id):
    return f'conversation:{conversation_id}'


def get_or_create_conversation(room_type, student_id, teacher_id=None):
    conversation = ChatConversation.query.filter_by(
        room_type=room_type,
        student_id=student_id,
        teacher_id=teacher_id,
    ).first()
    if conversation:
        return conversation
    conversation = ChatConversation(room_type=room_type, student_id=student_id, teacher_id=teacher_id)
    db.session.add(conversation)
    db.session.commit()
    return conversation


def can_access_conversation(conversation):
    if current_user.role == 'student':
        return conversation.student_id == current_user.id
    if current_user.role == 'parent':
        return conversation.room_type == 'parent' and conversation.student_id == current_user.id
    if current_user.role == 'teacher':
        return conversation.teacher_id == current_user.id
    return False


def save_chat_message(conversation_id, sender_id, sender_role, content):
    message = ChatMessage(
        conversation_id=conversation_id,
        sender_id=sender_id,
        sender_role=sender_role,
        content=content.strip(),
    )
    conversation = ChatConversation.query.get(conversation_id)
    if conversation:
        conversation.updated_at = datetime.utcnow()
    db.session.add(message)
    db.session.commit()
    return message


def serialize_chat_message(message):
    return {
        'id': message.id,
        'sender_id': message.sender_id,
        'sender_role': message.sender_role,
        'content': message.content,
        'created_at': message.created_at.strftime('%d/%m/%Y %H:%M') if message.created_at else '',
    }


def masked_gemini_error(text, api_key):
    safe_text = text.replace(api_key, '***MASKED_KEY***') if api_key else text
    return safe_text.replace(f'api_key:{api_key}', 'api_key:***MASKED_KEY***') if api_key else safe_text


def ask_kbot(prompt):
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return 'Kbot chưa được cấu hình GEMINI_API_KEY. Bạn vẫn có thể ghi lại điều muốn tâm sự ở đây.'
    primary_model = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash').strip()
    fallback_model = os.environ.get('GEMINI_FALLBACK_MODEL', 'gemini-1.5-flash').strip()
    models = [model for model in [primary_model, fallback_model] if model]
    models = list(dict.fromkeys(models))
    payload = {
        'contents': [{
            'parts': [{
                'text': (
                    'Bạn là Kbot, trợ lý tâm lý học đường thân thiện cho học sinh. '
                    'Hãy phản hồi ngắn gọn, ấm áp, không chẩn đoán y khoa. '
                    'Nếu học sinh có nguy cơ tự hại hoặc nguy hiểm, khuyên liên hệ ngay thầy cô, phụ huynh hoặc số khẩn cấp địa phương. '
                    f'Học sinh nói: {prompt}'
                )
            }]
        }]
    }
    data = json.dumps(payload).encode('utf-8')
    last_http_code = None
    for model in models:
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}'
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=20) as response:
                    result = json.loads(response.read().decode('utf-8'))
                return result['candidates'][0]['content']['parts'][0]['text'].strip()
            except urllib.error.HTTPError as error:
                body = error.read().decode('utf-8', errors='replace')
                safe_body = masked_gemini_error(body, api_key)
                last_http_code = error.code
                print(f'Gemini API HTTP {error.code} ({model}, attempt {attempt + 1}): {safe_body}')
                if error.code in (429, 500, 502, 503, 504):
                    time.sleep(1 + attempt)
                    continue
                return f'Kbot chưa kết nối được Gemini (HTTP {error.code}). Kiểm tra API key, quota hoặc model Gemini.'
            except urllib.error.URLError as error:
                print(f'Gemini API network error ({model}): {error}')
                return 'Kbot chưa kết nối được Gemini do lỗi mạng. Bạn kiểm tra internet hoặc thử lại sau.'
            except (KeyError, IndexError, TimeoutError, json.JSONDecodeError) as error:
                print(f'Gemini API response parse error ({model}): {error}')
                break
    if last_http_code in (429, 500, 502, 503, 504):
        return 'Kbot đang quá tải tạm thời. Bạn thử gửi lại sau một chút nhé.'
    return 'Kbot đang hơi bận. Bạn thử gửi lại sau một chút nhé.'


def daily_emotion_prompt():
    prompts = [
        'Hôm nay điều gì khiến bạn mỉm cười?',
        'Điều gì hôm nay làm bạn thấy nhẹ lòng hơn?',
        'Nếu chọn một từ cho hôm nay, bạn sẽ chọn từ nào?',
        'Bạn muốn cảm ơn bản thân vì điều gì hôm nay?',
        'Có điều gì bạn muốn buông xuống trước khi nghỉ ngơi không?',
    ]
    return prompts[datetime.utcnow().timetuple().tm_yday % len(prompts)]


def emotion_weekly_entries(student_id):
    return EmotionEntry.query.filter_by(student_id=student_id).order_by(EmotionEntry.created_at.desc()).limit(7).all()[::-1]


def recent_emotion_entries(student_id, limit=8):
    entries = EmotionEntry.query.filter_by(student_id=student_id).order_by(EmotionEntry.created_at.desc()).limit(limit).all()
    result = []
    for entry in entries:
        try:
            triggers = json.loads(entry.triggers_json or '[]')
        except json.JSONDecodeError:
            triggers = []
        result.append({'entry': entry, 'triggers': triggers})
    return result


def get_or_create_student_profile(student_id):
    profile = StudentProfile.query.filter_by(student_id=student_id).first()
    if profile:
        return profile
    profile = StudentProfile(student_id=student_id)
    db.session.add(profile)
    db.session.commit()
    return profile


def get_or_create_teacher_profile(teacher_id):
    profile = TeacherProfile.query.filter_by(teacher_id=teacher_id).first()
    if profile:
        return profile
    profile = TeacherProfile(teacher_id=teacher_id)
    db.session.add(profile)
    db.session.commit()
    return profile


def emotion_risk_percent(entries):
    if not entries:
        return None
    mood_base = {
        'vui': 10,
        'binh_than': 18,
        'cang_thang': 45,
        'lo_lang': 50,
        'buon': 48,
    }
    scores = []
    for entry in entries:
        intensity = max(1, min(int(entry.intensity or 1), 5))
        base = mood_base.get(entry.mood, 28)
        if entry.mood in ['cang_thang', 'lo_lang', 'buon']:
            score = base + intensity * 9
        elif entry.mood == 'vui':
            score = max(0, base + (5 - intensity) * 4)
        else:
            score = base + abs(3 - intensity) * 5
        scores.append(max(0, min(score, 100)))
    return round(sum(scores) / len(scores))


def chat_risk_percent(messages):
    if not messages:
        return None
    severe_keywords = ['tự hại', 'muốn chết', 'không muốn sống', 'tự tử', 'khủng hoảng']
    watch_keywords = [
        'áp lực', 'stress', 'căng thẳng', 'lo lắng', 'buồn', 'mệt', 'sợ',
        'khóc', 'cô đơn', 'bắt nạt', 'không ổn', 'gia đình', 'tuyệt vọng',
    ]
    student_messages = [message for message in messages if message.sender_role == 'student']
    if not student_messages:
        return None
    hits = 0
    severe_hit = False
    for message in student_messages:
        content = (message.content or '').lower()
        if any(keyword in content for keyword in severe_keywords):
            severe_hit = True
        if any(keyword in content for keyword in watch_keywords):
            hits += 1
    if severe_hit:
        return 90
    return min(100, round((hits / len(student_messages)) * 100))


def psychology_status_label(percent):
    if percent is None:
        return 'Chưa có dữ liệu'
    if percent <= 20:
        return 'Ổn định'
    if percent <= 40:
        return 'Theo dõi nhẹ'
    if percent <= 60:
        return 'Cần hỗ trợ'
    if percent <= 80:
        return 'Cần can thiệp'
    return 'Khẩn cấp'


def student_psychology_status(student_id):
    components = []
    latest_submission = PsychologySubmission.query.filter_by(student_id=student_id).order_by(PsychologySubmission.created_at.desc()).first()
    if latest_submission:
        components.append((latest_submission.percent, 0.5))

    emotion_entries = EmotionEntry.query.filter_by(student_id=student_id).order_by(EmotionEntry.created_at.desc()).limit(14).all()
    emotion_score = emotion_risk_percent(emotion_entries)
    if emotion_score is not None:
        components.append((emotion_score, 0.3))

    conversations = ChatConversation.query.filter_by(student_id=student_id).all()
    conversation_ids = [conversation.id for conversation in conversations]
    chat_messages = []
    if conversation_ids:
        chat_messages = ChatMessage.query.filter(ChatMessage.conversation_id.in_(conversation_ids)).order_by(ChatMessage.created_at.desc()).limit(50).all()
    chat_score = chat_risk_percent(chat_messages)
    if chat_score is not None:
        components.append((chat_score, 0.2))

    if not components:
        return {'percent': None, 'label': 'Chưa có dữ liệu', 'class': 'muted'}
    total_weight = sum(weight for _, weight in components)
    percent = round(sum(score * weight for score, weight in components) / total_weight)
    label = psychology_status_label(percent)
    status_class = 'safe'
    if percent > 40:
        status_class = 'watch'
    if percent > 60:
        status_class = 'alert'
    if percent > 80:
        status_class = 'danger'
    return {'percent': percent, 'label': label, 'class': status_class}


def teacher_student_rows():
    students = User.query.filter_by(role='student').order_by(User.id.asc()).all()
    profiles = StudentProfile.query.filter(StudentProfile.student_id.in_([student.id for student in students])).all() if students else []
    profiles_by_student = {profile.student_id: profile for profile in profiles}
    rows = []
    for index, student in enumerate(students, start=1):
        profile = profiles_by_student.get(student.id)
        full_name = profile.full_name if profile and profile.full_name else student.username
        status = student_psychology_status(student.id)
        rows.append({
            'stt': index,
            'student_id': student.id,
            'full_name': full_name,
            'is_active': student.is_active,
            'account_status': 'Đã kích hoạt' if student.is_active else 'Chưa kích hoạt',
            'psychology': status,
        })
    return rows


def register_pdf_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        os.path.join(app.root_path, 'static', 'fonts', 'DejaVuSans.ttf'),
        r'C:\Windows\Fonts\arial.ttf',
        r'C:\Windows\Fonts\calibri.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]
    for font_path in candidates:
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('AppFont', font_path))
            return 'AppFont'
    return 'Helvetica'


def build_teacher_students_pdf(rows):
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    font_name = register_pdf_font()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('AppTitle', parent=styles['Title'], fontName=font_name, fontSize=16, leading=20)
    cell_style = ParagraphStyle('AppCell', parent=styles['BodyText'], fontName=font_name, fontSize=9, leading=12)
    header_style = ParagraphStyle('AppHeader', parent=cell_style, textColor=colors.white)

    data = [[
        Paragraph('STT', header_style),
        Paragraph('Mã học sinh', header_style),
        Paragraph('Họ và tên', header_style),
        Paragraph('Trạng thái', header_style),
        Paragraph('Trạng thái tâm lí', header_style),
    ]]
    for row in rows:
        psychology = row['psychology']
        psychology_text = 'Chưa có dữ liệu' if psychology['percent'] is None else f"{psychology['percent']}% - {psychology['label']}"
        data.append([
            Paragraph(str(row['stt']), cell_style),
            Paragraph(str(row['student_id']), cell_style),
            Paragraph(escape(str(row['full_name'])), cell_style),
            Paragraph(escape(row['account_status']), cell_style),
            Paragraph(escape(psychology_text), cell_style),
        ])

    table = Table(data, colWidths=[18 * mm, 32 * mm, 70 * mm, 46 * mm, 70 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#111827')),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#dbe3ef')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    story = [
        Paragraph('Bảng quản lý học sinh', title_style),
        Spacer(1, 8),
        Paragraph(f'Xuất lúc: {datetime.now().strftime("%d/%m/%Y %H:%M")}', cell_style),
        Spacer(1, 12),
        table,
    ]
    doc.build(story)
    buffer.seek(0)
    return buffer


@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter((User.username==form.username.data)|(User.email==form.email.data)).first():
            flash('Tên đăng nhập hoặc email đã tồn tại', 'danger')
            return render_template('register.html', form=form)
        u = User(username=form.username.data, email=form.email.data, role=form.role.data)
        u.account_id = User.next_account_id()
        u.set_password(form.password.data)
        db.session.add(u)
        db.session.commit()
        flash('Đăng ký thành công. Vui lòng đăng nhập.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET','POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        selected_role = form.role.data or request.form.get('role')
        if not selected_role:
            flash('Vui lòng chọn loại tài khoản trước khi đăng nhập', 'warning')
            return render_template('login.html', form=form)
        user = User.query.filter_by(email=form.email.data).first()
        if not user:
            flash('Tài khoản hoặc mật khẩu không đúng', 'danger')
            return render_template('login.html', form=form)
        if user.role != selected_role:
            flash('Loại tài khoản không khớp. Vui lòng chọn đúng loại.', 'danger')
            return render_template('login.html', form=form)
        if not user.is_active:
            flash('Tài khoản đã bị thu hồi. Vui lòng liên hệ quản trị.', 'danger')
            return render_template('login.html', form=form)
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Đăng nhập thành công', 'success')
            return redirect(url_for('dashboard'))
        flash('Tài khoản hoặc mật khẩu không đúng', 'danger')
    return render_template('login.html', form=form)

@app.route('/dashboard')
@login_required
def dashboard():
    student_profile = None
    parent_teachers = []
    if current_user.role == 'student':
        student_profile = get_or_create_student_profile(current_user.id)
    if current_user.role == 'parent':
        parent_teachers = User.query.filter_by(role='teacher', is_active=True).order_by(User.username).all()
    return render_template('dashboard.html', student_profile=student_profile, parent_teachers=parent_teachers)


@app.route('/teacher/students')
@login_required
def teacher_students():
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    rows = teacher_student_rows()
    return render_template('teacher_students.html', rows=rows)


@app.route('/teacher/students/export.pdf')
@login_required
def teacher_students_pdf():
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    rows = teacher_student_rows()
    try:
        pdf_buffer = build_teacher_students_pdf(rows)
    except ImportError:
        flash('Chưa cài thư viện reportlab để xuất PDF. Vui lòng cài reportlab rồi thử lại.', 'warning')
        return redirect(url_for('teacher_students'))
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='bang-quan-ly-hoc-sinh.pdf',
    )


@app.route('/contact-admin', methods=['GET','POST'])
@login_required
def contact_admin():
    # only teacher and student can contact admin
    if current_user.role not in ('teacher','student'):
        flash('Chức năng này chỉ dành cho giáo viên và học sinh', 'warning')
        return redirect(url_for('dashboard'))
    form = MessageForm()
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        flash('Không có quản trị viên trong hệ thống', 'danger')
        return redirect(url_for('dashboard'))
    if form.validate_on_submit():
        m = Message(sender_id=current_user.id, recipient_id=admin.id, content=form.content.data)
        db.session.add(m)
        db.session.commit()
        flash('Đã gửi tin nhắn tới quản trị', 'success')
        return redirect(url_for('contact_admin'))
    messages = Message.query.filter_by(
        sender_id=current_user.id,
        recipient_id=admin.id,
        reply_to=None,
    ).order_by(Message.created_at.desc()).all()
    replies_by_message = defaultdict(list)
    message_ids = [message.id for message in messages]
    if message_ids:
        replies = Message.query.filter(Message.reply_to.in_(message_ids)).order_by(Message.created_at.asc()).all()
        for reply in replies:
            replies_by_message[reply.reply_to].append(reply)
    return render_template('contact_admin.html', form=form, messages=messages, replies_by_message=replies_by_message)


@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'admin':
        flash('Bạn không có quyền truy cập trang này', 'danger')
        return redirect(url_for('dashboard'))
    users = User.query.order_by(User.role, User.id).all()
    return render_template('admin_users.html', users=users)


@app.route('/admin/user/<int:user_id>', methods=['GET','POST'])
@login_required
def admin_user_manage(user_id):
    if current_user.role != 'admin':
        flash('Bạn không có quyền truy cập trang này', 'danger')
        return redirect(url_for('dashboard'))
    user = User.query.get_or_404(user_id)
    form = ChangePasswordForm()
    if request.method == 'POST' and request.form.get('action') == 'deactivate':
        user.is_active = False
        db.session.commit()
        flash('Tài khoản đã bị thu hồi (deactivated)', 'info')
        return redirect(url_for('admin_user_manage', user_id=user.id))
    if request.method == 'POST' and request.form.get('action') == 'activate':
        user.is_active = True
        db.session.commit()
        flash('Tài khoản đã được cấp lại (activated)', 'success')
        return redirect(url_for('admin_user_manage', user_id=user.id))
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Mật khẩu đã được cập nhật cho người dùng', 'success')
        return redirect(url_for('admin_user_manage', user_id=user.id))
    return render_template('admin_user_manage.html', user=user, form=form)


@app.route('/admin/stats')
@login_required
def admin_stats():
    if current_user.role != 'admin':
        flash('Bạn không có quyền truy cập trang này', 'danger')
        return redirect(url_for('dashboard'))
    roles = ['admin','teacher','student','parent']
    counts = {r: User.query.filter_by(role=r).count() for r in roles}
    colors = {
        'admin': '#2563eb',
        'teacher': '#16a34a',
        'student': '#f59e0b',
        'parent': '#ec4899',
    }
    total_users = sum(counts.values())
    chart_items = []
    start = 0
    gradient_parts = []
    for role in roles:
        count = counts[role]
        percent = round(count / total_users * 100, 1) if total_users else 0
        end = start + percent
        if total_users:
            gradient_parts.append(f"{colors[role]} {start}% {end}%")
        chart_items.append({
            'role': role,
            'count': count,
            'percent': percent,
            'color': colors[role],
        })
        start = end
    chart_gradient = ', '.join(gradient_parts) if gradient_parts else '#e5e7eb 0% 100%'
    return render_template(
        'admin_stats.html',
        counts=counts,
        chart_items=chart_items,
        chart_gradient=chart_gradient,
        total_users=total_users,
    )


@app.route('/admin/chat', methods=['GET','POST'])
@login_required
def admin_chat():
    if current_user.role != 'admin':
        flash('Bạn không có quyền truy cập trang này', 'danger')
        return redirect(url_for('dashboard'))
    messages = Message.query.join(User, Message.sender_id == User.id).filter(
        User.role.in_(['teacher', 'student']),
        Message.reply_to.is_(None),
    ).order_by(Message.created_at.desc()).all()
    replies_by_message = defaultdict(list)
    message_ids = [message.id for message in messages]
    if message_ids:
        replies = Message.query.filter(Message.reply_to.in_(message_ids)).order_by(Message.created_at.asc()).all()
        for reply in replies:
            replies_by_message[reply.reply_to].append(reply)
    sender_ids = sorted({message.sender_id for message in messages})
    users = User.query.filter(User.id.in_(sender_ids)).all() if sender_ids else []
    users_by_id = {user.id: user for user in users}
    return render_template(
        'admin_chat.html',
        messages=messages,
        replies_by_message=replies_by_message,
        users_by_id=users_by_id,
    )


@app.route('/admin/reply/<int:message_id>', methods=['POST'])
@login_required
def admin_reply(message_id):
    if current_user.role != 'admin':
        flash('Bạn không có quyền gửi trả lời', 'danger')
        return redirect(url_for('admin_chat'))
    original = Message.query.get_or_404(message_id)
    content = (request.form.get('reply') or '').strip()
    if not content:
        flash('Nội dung trả lời rỗng', 'warning')
        return redirect(url_for('admin_chat'))
    reply = Message(sender_id=current_user.id, recipient_id=original.sender_id, content=content, reply_to=original.id)
    db.session.add(reply)
    db.session.commit()
    flash('Đã gửi trả lời', 'success')
    return redirect(url_for('admin_chat'))

@app.route('/admin/create-teacher', methods=['GET','POST'])
@login_required
def create_teacher():
    if current_user.role != 'admin':
        flash('Bạn không có quyền truy cập trang này', 'danger')
        return redirect(url_for('dashboard'))
    form = CreateTeacherForm()
    if form.validate_on_submit():
        if User.query.filter((User.username==form.username.data)|(User.email==form.email.data)).first():
            flash('Tên đăng nhập hoặc email đã tồn tại', 'danger')
            return render_template('admin_create_teacher.html', form=form)
        u = User(username=form.username.data, email=form.email.data, role='teacher')
        u.account_id = User.next_account_id()
        u.set_password(form.password.data)
        db.session.add(u)
        db.session.commit()
        flash('Tạo tài khoản giáo viên thành công', 'success')
        return redirect(url_for('dashboard'))
    return render_template('admin_create_teacher.html', form=form)


@app.route('/psychology/quizzes')
@login_required
def psychology_quizzes():
    if current_user.role == 'teacher':
        return redirect(url_for('teacher_quizzes'))
    if current_user.role == 'student':
        return redirect(url_for('student_quizzes'))
    flash('Chức năng trắc nghiệm tâm lý dành cho giáo viên và học sinh', 'warning')
    return redirect(url_for('dashboard'))


@app.route('/teacher/psychology/quizzes')
@login_required
def teacher_quizzes():
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    topics = PsychologyTopic.query.filter_by(teacher_id=current_user.id).order_by(PsychologyTopic.updated_at.desc()).all()
    question_counts = {topic.id: topic_question_count(topic.id) for topic in topics}
    submission_counts = {
        topic.id: PsychologySubmission.query.filter_by(topic_id=topic.id).count()
        for topic in topics
    }
    return render_template(
        'teacher_quizzes.html',
        topics=topics,
        question_counts=question_counts,
        submission_counts=submission_counts,
    )


@app.route('/teacher/psychology/quizzes/new', methods=['GET', 'POST'])
@login_required
def teacher_quiz_new():
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        description = (request.form.get('description') or '').strip()
        questions = collect_quiz_questions()
        if not title:
            flash('Vui lòng nhập chủ đề trắc nghiệm', 'warning')
        elif questions is None:
            flash('Mỗi câu hỏi cần đủ nội dung và 4 đáp án A/B/C/D', 'warning')
        elif not questions:
            flash('Vui lòng nhập ít nhất một câu hỏi', 'warning')
        else:
            topic = PsychologyTopic(title=title, description=description, teacher_id=current_user.id)
            db.session.add(topic)
            db.session.flush()
            for question in questions:
                db.session.add(PsychologyQuestion(topic_id=topic.id, **question))
            db.session.commit()
            flash('Đã upload chủ đề trắc nghiệm cho học sinh', 'success')
            return redirect(url_for('teacher_quizzes'))
    return render_template('teacher_quiz_form.html', topic=None, questions=[])


@app.route('/teacher/psychology/quizzes/<int:topic_id>/edit', methods=['GET', 'POST'])
@login_required
def teacher_quiz_edit(topic_id):
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    topic = PsychologyTopic.query.get_or_404(topic_id)
    if topic.teacher_id != current_user.id:
        flash('Bạn chỉ có thể chỉnh sửa chủ đề của mình', 'danger')
        return redirect(url_for('teacher_quizzes'))
    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        description = (request.form.get('description') or '').strip()
        questions = collect_quiz_questions()
        if not title:
            flash('Vui lòng nhập chủ đề trắc nghiệm', 'warning')
        elif questions is None:
            flash('Mỗi câu hỏi cần đủ nội dung và 4 đáp án A/B/C/D', 'warning')
        elif not questions:
            flash('Vui lòng nhập ít nhất một câu hỏi', 'warning')
        else:
            topic.title = title
            topic.description = description
            topic.updated_at = datetime.utcnow()
            PsychologyQuestion.query.filter_by(topic_id=topic.id).delete()
            for question in questions:
                db.session.add(PsychologyQuestion(topic_id=topic.id, **question))
            db.session.commit()
            flash('Đã cập nhật chủ đề trắc nghiệm', 'success')
            return redirect(url_for('teacher_quizzes'))
    questions = PsychologyQuestion.query.filter_by(topic_id=topic.id).order_by(PsychologyQuestion.position, PsychologyQuestion.id).all()
    return render_template('teacher_quiz_form.html', topic=topic, questions=questions)


@app.route('/teacher/psychology/quizzes/<int:topic_id>/results')
@login_required
def teacher_quiz_results(topic_id):
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    topic = PsychologyTopic.query.get_or_404(topic_id)
    if topic.teacher_id != current_user.id:
        flash('Bạn chỉ có thể xem kết quả chủ đề của mình', 'danger')
        return redirect(url_for('teacher_quizzes'))
    submissions = PsychologySubmission.query.filter_by(topic_id=topic.id).order_by(PsychologySubmission.created_at.desc()).all()
    student_ids = sorted({submission.student_id for submission in submissions})
    students = User.query.filter(User.id.in_(student_ids)).all() if student_ids else []
    students_by_id = {student.id: student for student in students}
    return render_template(
        'teacher_quiz_results.html',
        topic=topic,
        submissions=submissions,
        students_by_id=students_by_id,
        psychology_rating=psychology_rating,
    )


@app.route('/student/psychology/quizzes')
@login_required
def student_quizzes():
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    topics = PsychologyTopic.query.filter_by(is_published=True).order_by(PsychologyTopic.updated_at.desc()).all()
    question_counts = {topic.id: topic_question_count(topic.id) for topic in topics}
    latest_submissions = {}
    for topic in topics:
        latest_submissions[topic.id] = PsychologySubmission.query.filter_by(
            topic_id=topic.id,
            student_id=current_user.id,
        ).order_by(PsychologySubmission.created_at.desc()).first()
    return render_template(
        'student_quizzes.html',
        topics=topics,
        question_counts=question_counts,
        latest_submissions=latest_submissions,
    )


@app.route('/student/psychology/quizzes/<int:topic_id>', methods=['GET', 'POST'])
@login_required
def student_quiz_take(topic_id):
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    topic = PsychologyTopic.query.get_or_404(topic_id)
    questions = PsychologyQuestion.query.filter_by(topic_id=topic.id).order_by(PsychologyQuestion.position, PsychologyQuestion.id).all()
    if not topic.is_published or not questions:
        flash('Bài trắc nghiệm này chưa sẵn sàng', 'warning')
        return redirect(url_for('student_quizzes'))
    if request.method == 'POST':
        answer_scores = {'a': 0, 'b': 1, 'c': 2, 'd': 3}
        answers = {}
        total = 0
        for question in questions:
            answer = (request.form.get(f'question_{question.id}') or '').lower()
            if answer not in answer_scores:
                flash('Vui lòng trả lời đầy đủ tất cả câu hỏi', 'warning')
                return render_template('student_quiz_take.html', topic=topic, questions=questions)
            answers[str(question.id)] = answer
            total += answer_scores[answer]
        max_score = len(questions) * 3
        percent = round((total / max_score) * 100) if max_score else 0
        rating = psychology_rating(percent)
        submission = PsychologySubmission(
            topic_id=topic.id,
            student_id=current_user.id,
            score=total,
            percent=percent,
            level=rating['level'],
            answers_json=json.dumps(answers),
        )
        db.session.add(submission)
        db.session.commit()
        flash('Đã nộp bài trắc nghiệm', 'success')
        return redirect(url_for('student_quiz_result', submission_id=submission.id))
    return render_template('student_quiz_take.html', topic=topic, questions=questions)


@app.route('/student/psychology/results/<int:submission_id>')
@login_required
def student_quiz_result(submission_id):
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    submission = PsychologySubmission.query.get_or_404(submission_id)
    if submission.student_id != current_user.id:
        flash('Bạn chỉ có thể xem kết quả của mình', 'danger')
        return redirect(url_for('student_quizzes'))
    topic = PsychologyTopic.query.get_or_404(submission.topic_id)
    return render_template(
        'student_quiz_result.html',
        topic=topic,
        submission=submission,
        rating=psychology_rating(submission.percent),
        ratings=all_psychology_ratings(),
    )


@app.route('/career')
@login_required
def career_home():
    if current_user.role == 'teacher':
        return redirect(url_for('teacher_career_tests'))
    if current_user.role == 'student':
        return redirect(url_for('student_self_discovery'))
    flash('Chức năng hướng nghiệp dành cho giáo viên và học sinh', 'warning')
    return redirect(url_for('dashboard'))


@app.route('/student/career/self-discovery')
@login_required
def student_self_discovery():
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    tests = CareerTest.query.filter_by(is_published=True).order_by(CareerTest.updated_at.desc()).limit(5).all()
    question_counts = {test.id: career_question_count(test.id) for test in tests}
    latest_submissions = {}
    for test in tests:
        latest_submissions[test.id] = CareerSubmission.query.filter_by(
            test_id=test.id,
            student_id=current_user.id,
        ).order_by(CareerSubmission.created_at.desc()).first()
    entry_count = EmotionEntry.query.filter_by(student_id=current_user.id).count()
    test_count = CareerSubmission.query.filter_by(student_id=current_user.id).count()
    discovery_percent = min(100, 18 + entry_count * 3 + test_count * 18)
    return render_template(
        'student_career_self_discovery.html',
        tests=tests,
        question_counts=question_counts,
        latest_submissions=latest_submissions,
        entry_count=entry_count,
        test_count=test_count,
        discovery_percent=discovery_percent,
        personality=career_personality_summary(current_user.id),
        insights=career_insights(current_user.id),
        trends=career_emotion_trends(current_user.id),
    )


@app.route('/student/career/tests/<int:test_id>', methods=['GET', 'POST'])
@login_required
def student_career_test_take(test_id):
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    test = CareerTest.query.get_or_404(test_id)
    questions = CareerQuestion.query.filter_by(test_id=test.id).order_by(CareerQuestion.position, CareerQuestion.id).all()
    if not test.is_published or not questions:
        flash('Bài khám phá này chưa sẵn sàng', 'warning')
        return redirect(url_for('student_self_discovery'))
    if request.method == 'POST':
        answer_scores = {'a': 1, 'b': 2, 'c': 3, 'd': 4}
        answers = {}
        total = 0
        for question in questions:
            answer = (request.form.get(f'question_{question.id}') or '').lower()
            if answer not in answer_scores:
                flash('Vui lòng trả lời đầy đủ tất cả câu hỏi', 'warning')
                return render_template('student_career_test_take.html', test=test, questions=questions)
            answers[str(question.id)] = answer
            total += answer_scores[answer]
        max_score = len(questions) * 4
        percent = round((total / max_score) * 100) if max_score else 0
        submission = CareerSubmission(
            test_id=test.id,
            student_id=current_user.id,
            score=total,
            percent=percent,
            answers_json=json.dumps(answers),
        )
        db.session.add(submission)
        db.session.commit()
        flash('Đã lưu kết quả khám phá', 'success')
        return redirect(url_for('student_self_discovery'))
    return render_template('student_career_test_take.html', test=test, questions=questions)


@app.route('/student/career/library')
@login_required
def student_career_library():
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    jobs = career_library_data()
    fields = ['Tất cả'] + sorted({job['field'] for job in jobs})
    return render_template('student_career_library.html', jobs=jobs, fields=fields)


@app.route('/student/career/library/ask', methods=['POST'])
@login_required
def student_career_ask():
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    job_id = request.form.get('job_id', type=int)
    question = (request.form.get('question') or '').strip()
    job = CareerJob.query.filter_by(id=job_id, is_published=True).first()
    if not job:
        flash('Nghề này chưa sẵn sàng để gửi câu hỏi', 'warning')
        return redirect(url_for('student_career_library'))
    if not question:
        flash('Vui lòng nhập câu hỏi trước khi gửi', 'warning')
        return redirect(url_for('student_career_library'))
    inquiry = CareerInquiry(
        job_id=job.id,
        student_id=current_user.id,
        teacher_id=job.teacher_id,
        question=question,
    )
    db.session.add(inquiry)
    db.session.commit()
    flash('Đã gửi câu hỏi đến giáo viên phụ trách nghề này', 'success')
    return redirect(url_for('student_inbox'))


@app.route('/student/inbox')
@login_required
def student_inbox():
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    inquiries = CareerInquiry.query.filter_by(student_id=current_user.id).order_by(CareerInquiry.created_at.desc()).all()
    job_ids = sorted({item.job_id for item in inquiries})
    teacher_ids = sorted({item.teacher_id for item in inquiries})
    jobs_by_id = {job.id: job for job in CareerJob.query.filter(CareerJob.id.in_(job_ids)).all()} if job_ids else {}
    teachers_by_id = {user.id: user for user in User.query.filter(User.id.in_(teacher_ids)).all()} if teacher_ids else {}
    return render_template(
        'student_inbox.html',
        inquiries=inquiries,
        jobs_by_id=jobs_by_id,
        teachers_by_id=teachers_by_id,
    )


@app.route('/student/career/learning-path')
@login_required
def student_learning_path():
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    paths = CareerLearningPath.query.filter_by(is_published=True).order_by(CareerLearningPath.updated_at.desc()).all()
    selected_path = None
    stages = []
    tasks_by_stage = {}
    skills = []
    total_tasks = 0
    done_tasks = 0
    path_id = request.args.get('path_id', type=int)
    if path_id:
        selected_path = CareerLearningPath.query.filter_by(id=path_id, is_published=True).first_or_404()
        stages, tasks_by_stage, skills, total_tasks, done_tasks = learning_path_details(selected_path.id)
    return render_template(
        'student_learning_path.html',
        paths=paths,
        selected_path=selected_path,
        stages=stages,
        tasks_by_stage=tasks_by_stage,
        skills=skills,
        total_tasks=total_tasks,
        done_tasks=done_tasks,
    )


@app.route('/teacher/career/learning-paths')
@login_required
def teacher_learning_paths():
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    paths = CareerLearningPath.query.filter_by(teacher_id=current_user.id).order_by(CareerLearningPath.updated_at.desc()).all()
    return render_template('teacher_learning_paths.html', paths=paths)


@app.route('/teacher/career/learning-paths/new', methods=['GET', 'POST'])
@login_required
def teacher_learning_path_new():
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    default_stages, default_skills = default_learning_path_payload()
    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        summary = (request.form.get('summary') or '').strip()
        icon = (request.form.get('icon') or '').strip()
        color = (request.form.get('color') or 'purple').strip()
        goal_label = (request.form.get('goal_label') or '').strip()
        completion_percent = request.form.get('completion_percent', type=int) or 0
        stages, skills = parse_learning_path_payload(request.form.get('stages_json'), request.form.get('skills_json'))
        if not title or not summary:
            flash('Vui lòng nhập tên ngành và mô tả ngắn', 'warning')
        elif stages is None or skills is None:
            flash('Dữ liệu giai đoạn/kỹ năng phải là JSON hợp lệ', 'warning')
        else:
            path = CareerLearningPath(
                teacher_id=current_user.id,
                title=title,
                summary=summary,
                icon=icon,
                color=color,
                goal_label=goal_label or title,
                completion_percent=max(0, min(100, completion_percent)),
                is_published=True,
            )
            db.session.add(path)
            db.session.flush()
            replace_learning_path_details(path, stages, skills)
            db.session.commit()
            flash('Đã upload lộ trình học tập', 'success')
            return redirect(url_for('teacher_learning_paths'))
    return render_template('teacher_learning_path_form.html', path=None, stages_json=default_stages, skills_json=default_skills)


@app.route('/teacher/career/learning-paths/<int:path_id>/edit', methods=['GET', 'POST'])
@login_required
def teacher_learning_path_edit(path_id):
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    path = CareerLearningPath.query.get_or_404(path_id)
    if path.teacher_id != current_user.id:
        flash('Bạn chỉ có thể chỉnh sửa lộ trình mình upload', 'danger')
        return redirect(url_for('teacher_learning_paths'))
    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        summary = (request.form.get('summary') or '').strip()
        icon = (request.form.get('icon') or '').strip()
        color = (request.form.get('color') or 'purple').strip()
        goal_label = (request.form.get('goal_label') or '').strip()
        completion_percent = request.form.get('completion_percent', type=int) or 0
        stages, skills = parse_learning_path_payload(request.form.get('stages_json'), request.form.get('skills_json'))
        if not title or not summary:
            flash('Vui lòng nhập tên ngành và mô tả ngắn', 'warning')
        elif stages is None or skills is None:
            flash('Dữ liệu giai đoạn/kỹ năng phải là JSON hợp lệ', 'warning')
        else:
            path.title = title
            path.summary = summary
            path.icon = icon
            path.color = color
            path.goal_label = goal_label or title
            path.completion_percent = max(0, min(100, completion_percent))
            path.updated_at = datetime.utcnow()
            replace_learning_path_details(path, stages, skills)
            db.session.commit()
            flash('Đã cập nhật lộ trình học tập', 'success')
            return redirect(url_for('teacher_learning_paths'))
    stages, tasks_by_stage, skills, _, _ = learning_path_details(path.id)
    stages_data = []
    for stage in stages:
        stages_data.append({
            'year_label': stage.year_label,
            'subtitle': stage.subtitle,
            'title': stage.title,
            'status': stage.status,
            'is_open': stage.is_open,
            'tasks': [
                {
                    'title': task.title,
                    'subtitle': task.subtitle,
                    'type': task.task_type,
                    'done': task.is_done,
                }
                for task in tasks_by_stage.get(stage.id, [])
            ],
        })
    skills_data = [
        {'name': skill.name, 'level': skill.level_label, 'percent': skill.percent, 'color': skill.color}
        for skill in skills
    ]
    return render_template(
        'teacher_learning_path_form.html',
        path=path,
        stages_json=json.dumps(stages_data, ensure_ascii=False, indent=2),
        skills_json=json.dumps(skills_data, ensure_ascii=False, indent=2),
    )


@app.route('/student/community/forum', methods=['GET', 'POST'])
@login_required
def student_forum():
    if not role_required('student', 'teacher'):
        return redirect(url_for('dashboard'))
    categories = ['Tất cả', 'Học tập', 'Cảm xúc', 'Hướng nghiệp', 'Cuộc sống']
    can_interact = current_user.role == 'student'
    if request.method == 'POST' and not can_interact:
        flash('Giáo viên có thể xem diễn đàn học sinh nhưng không đăng bài tại đây', 'warning')
        return redirect(url_for('student_forum'))
    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        content = (request.form.get('content') or '').strip()
        category = (request.form.get('category') or 'Cuộc sống').strip()
        if category not in categories[1:]:
            category = 'Cuộc sống'
        if not title or not content:
            flash('Vui lòng nhập tiêu đề và nội dung bài viết', 'warning')
        else:
            post = ForumPost(
                student_id=current_user.id,
                title=title,
                content=content,
                category=category,
                is_anonymous=request.form.get('is_anonymous') == 'on',
            )
            db.session.add(post)
            db.session.commit()
            flash('Đã đăng bài vào diễn đàn học sinh', 'success')
            return redirect(url_for('student_forum'))
    active_category = request.args.get('category', 'Tất cả')
    query = ForumPost.query
    if active_category in categories[1:]:
        query = query.filter_by(category=active_category)
    posts = query.order_by(ForumPost.created_at.desc()).limit(30).all()
    post_ids = [post.id for post in posts]
    student_ids = sorted({post.student_id for post in posts})
    comments_by_post = defaultdict(list)
    if post_ids:
        comments = ForumComment.query.filter(ForumComment.post_id.in_(post_ids)).order_by(ForumComment.created_at.asc()).all()
        for comment in comments:
            comments_by_post[comment.post_id].append(comment)
            student_ids.append(comment.student_id)
    users_by_id = {user.id: user for user in User.query.filter(User.id.in_(sorted(set(student_ids)))).all()} if student_ids else {}
    my_reactions = {}
    if post_ids:
        reactions = ForumReaction.query.filter(
            ForumReaction.post_id.in_(post_ids),
            ForumReaction.student_id == current_user.id,
        ).all()
        my_reactions = {reaction.post_id: reaction.reaction_type for reaction in reactions}
    return render_template(
        'student_forum.html',
        categories=categories,
        active_category=active_category,
        posts=posts,
        comments_by_post=comments_by_post,
        users_by_id=users_by_id,
        my_reactions=my_reactions,
        can_interact=can_interact,
    )


@app.route('/student/community/forum/<int:post_id>/react', methods=['POST'])
@login_required
def student_forum_react(post_id):
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    reaction_type = (request.form.get('reaction_type') or '').strip()
    if reaction_type not in ('empathy', 'useful'):
        flash('Phản ứng không hợp lệ', 'warning')
        return redirect(url_for('student_forum'))
    post = ForumPost.query.get_or_404(post_id)
    reaction = ForumReaction.query.filter_by(post_id=post.id, student_id=current_user.id).first()
    if reaction and reaction.reaction_type == reaction_type:
        db.session.delete(reaction)
    elif reaction:
        reaction.reaction_type = reaction_type
    else:
        db.session.add(ForumReaction(post_id=post.id, student_id=current_user.id, reaction_type=reaction_type))
    db.session.commit()
    return redirect(url_for('student_forum', category=request.form.get('active_category') or 'Tất cả'))


@app.route('/student/community/forum/<int:post_id>/comment', methods=['POST'])
@login_required
def student_forum_comment(post_id):
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    post = ForumPost.query.get_or_404(post_id)
    content = (request.form.get('content') or '').strip()
    if not content:
        flash('Vui lòng nhập bình luận', 'warning')
    else:
        comment = ForumComment(
            post_id=post.id,
            student_id=current_user.id,
            content=content,
            is_anonymous=request.form.get('is_anonymous') == 'on',
        )
        db.session.add(comment)
        db.session.commit()
    return redirect(url_for('student_forum', category=request.form.get('active_category') or 'Tất cả'))


@app.route('/student/community/forum/<int:post_id>/report', methods=['POST'])
@login_required
def student_forum_report(post_id):
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    post = ForumPost.query.get_or_404(post_id)
    existing = ForumReport.query.filter_by(post_id=post.id, student_id=current_user.id).first()
    if not existing:
        report = ForumReport(
            post_id=post.id,
            student_id=current_user.id,
            reason=(request.form.get('reason') or 'Cần kiểm tra').strip(),
        )
        db.session.add(report)
        db.session.commit()
    flash('Đã ghi nhận báo cáo bài viết', 'info')
    return redirect(url_for('student_forum', category=request.form.get('active_category') or 'Tất cả'))


@app.route('/teacher/career/tests')
@login_required
def teacher_career_tests():
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    tests = CareerTest.query.filter_by(teacher_id=current_user.id).order_by(CareerTest.updated_at.desc()).all()
    question_counts = {test.id: career_question_count(test.id) for test in tests}
    submission_counts = {
        test.id: CareerSubmission.query.filter_by(test_id=test.id).count()
        for test in tests
    }
    return render_template(
        'teacher_career_tests.html',
        tests=tests,
        question_counts=question_counts,
        submission_counts=submission_counts,
    )


@app.route('/teacher/career/jobs')
@login_required
def teacher_career_jobs():
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    jobs = CareerJob.query.filter_by(teacher_id=current_user.id).order_by(CareerJob.updated_at.desc()).all()
    return render_template('teacher_career_jobs.html', jobs=jobs)


@app.route('/teacher/career/jobs/new', methods=['GET', 'POST'])
@login_required
def teacher_career_job_new():
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        data = collect_career_job_form()
        required = [data['name'], data['field'], data['summary'], data['work'], data['study'], data['salary'], data['demand'], data['personality']]
        if not all(required):
            flash('Vui lòng nhập đầy đủ thông tin nghề', 'warning')
        else:
            job = CareerJob(
                teacher_id=current_user.id,
                name=data['name'],
                field=data['field'],
                icon=data['icon'],
                summary=data['summary'],
                skills_json=json.dumps(data['skills'], ensure_ascii=False),
                work=data['work'],
                study=data['study'],
                salary=data['salary'],
                demand=data['demand'],
                personality=data['personality'],
                color=data['color'],
                is_featured=data['is_featured'],
            )
            db.session.add(job)
            db.session.commit()
            flash('Đã upload nghề vào thư viện nghề nghiệp', 'success')
            return redirect(url_for('teacher_career_jobs'))
    return render_template('teacher_career_job_form.html', job=None, skills_text='')


@app.route('/teacher/career/jobs/<int:job_id>/edit', methods=['GET', 'POST'])
@login_required
def teacher_career_job_edit(job_id):
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    job = CareerJob.query.get_or_404(job_id)
    if job.teacher_id != current_user.id:
        flash('Bạn chỉ có thể chỉnh sửa nghề mình upload', 'danger')
        return redirect(url_for('teacher_career_jobs'))
    if request.method == 'POST':
        data = collect_career_job_form()
        required = [data['name'], data['field'], data['summary'], data['work'], data['study'], data['salary'], data['demand'], data['personality']]
        if not all(required):
            flash('Vui lòng nhập đầy đủ thông tin nghề', 'warning')
        else:
            job.name = data['name']
            job.field = data['field']
            job.icon = data['icon']
            job.summary = data['summary']
            job.skills_json = json.dumps(data['skills'], ensure_ascii=False)
            job.work = data['work']
            job.study = data['study']
            job.salary = data['salary']
            job.demand = data['demand']
            job.personality = data['personality']
            job.color = data['color']
            job.is_featured = data['is_featured']
            job.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Đã cập nhật nghề', 'success')
            return redirect(url_for('teacher_career_jobs'))
    try:
        skills = json.loads(job.skills_json or '[]')
    except json.JSONDecodeError:
        skills = []
    return render_template('teacher_career_job_form.html', job=job, skills_text=', '.join(skills))


@app.route('/teacher/career/inquiries', methods=['GET', 'POST'])
@login_required
def teacher_career_inquiries():
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        inquiry_id = request.form.get('inquiry_id', type=int)
        reply = (request.form.get('reply') or '').strip()
        inquiry = CareerInquiry.query.filter_by(id=inquiry_id, teacher_id=current_user.id).first()
        if not inquiry:
            flash('Không tìm thấy câu hỏi cần phản hồi', 'warning')
        elif not reply:
            flash('Vui lòng nhập nội dung phản hồi', 'warning')
        else:
            inquiry.reply = reply
            inquiry.replied_at = datetime.utcnow()
            db.session.commit()
            flash('Đã gửi phản hồi vào hộp thư học sinh', 'success')
        return redirect(url_for('teacher_career_inquiries'))
    inquiries = CareerInquiry.query.filter_by(teacher_id=current_user.id).order_by(CareerInquiry.created_at.desc()).all()
    student_ids = sorted({item.student_id for item in inquiries})
    job_ids = sorted({item.job_id for item in inquiries})
    students_by_id = {user.id: user for user in User.query.filter(User.id.in_(student_ids)).all()} if student_ids else {}
    jobs_by_id = {job.id: job for job in CareerJob.query.filter(CareerJob.id.in_(job_ids)).all()} if job_ids else {}
    return render_template(
        'teacher_career_inquiries.html',
        inquiries=inquiries,
        students_by_id=students_by_id,
        jobs_by_id=jobs_by_id,
    )


@app.route('/teacher/career/tests/new', methods=['GET', 'POST'])
@login_required
def teacher_career_test_new():
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        description = (request.form.get('description') or '').strip()
        questions = collect_career_questions()
        if not title:
            flash('Vui lòng nhập tên bài khám phá', 'warning')
        elif questions is None:
            flash('Mỗi câu hỏi cần đủ nội dung và 4 đáp án A/B/C/D', 'warning')
        elif not questions:
            flash('Vui lòng nhập ít nhất một câu hỏi', 'warning')
        else:
            test = CareerTest(title=title, description=description, teacher_id=current_user.id)
            db.session.add(test)
            db.session.flush()
            for question in questions:
                db.session.add(CareerQuestion(test_id=test.id, **question))
            db.session.commit()
            flash('Đã upload bài khám phá hướng nghiệp', 'success')
            return redirect(url_for('teacher_career_tests'))
    return render_template('teacher_career_test_form.html', test=None, questions=[])


@app.route('/teacher/career/tests/<int:test_id>/edit', methods=['GET', 'POST'])
@login_required
def teacher_career_test_edit(test_id):
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    test = CareerTest.query.get_or_404(test_id)
    if test.teacher_id != current_user.id:
        flash('Bạn chỉ có thể chỉnh sửa bài khám phá của mình', 'danger')
        return redirect(url_for('teacher_career_tests'))
    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        description = (request.form.get('description') or '').strip()
        questions = collect_career_questions()
        if not title:
            flash('Vui lòng nhập tên bài khám phá', 'warning')
        elif questions is None:
            flash('Mỗi câu hỏi cần đủ nội dung và 4 đáp án A/B/C/D', 'warning')
        elif not questions:
            flash('Vui lòng nhập ít nhất một câu hỏi', 'warning')
        else:
            test.title = title
            test.description = description
            test.updated_at = datetime.utcnow()
            CareerQuestion.query.filter_by(test_id=test.id).delete()
            for question in questions:
                db.session.add(CareerQuestion(test_id=test.id, **question))
            db.session.commit()
            flash('Đã cập nhật bài khám phá hướng nghiệp', 'success')
            return redirect(url_for('teacher_career_tests'))
    questions = CareerQuestion.query.filter_by(test_id=test.id).order_by(CareerQuestion.position, CareerQuestion.id).all()
    return render_template('teacher_career_test_form.html', test=test, questions=questions)


@app.route('/teacher/life-skills')
@login_required
def teacher_life_skills():
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    lessons = LifeSkillLesson.query.filter_by(teacher_id=current_user.id).order_by(LifeSkillLesson.updated_at.desc()).all()
    completion_counts = {
        lesson.id: LifeSkillProgress.query.filter_by(lesson_id=lesson.id, is_completed=True).count()
        for lesson in lessons
    }
    return render_template('teacher_life_skills.html', lessons=lessons, completion_counts=completion_counts)


@app.route('/teacher/life-skills/new', methods=['GET', 'POST'])
@login_required
def teacher_life_skill_new():
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        data = collect_life_skill_lesson_form()
        required = [data['title'], data['skill_category'], data['video_url'], data['description']]
        if not all(required):
            flash('Vui lòng nhập tiêu đề, kỹ năng, link video và mô tả', 'warning')
        else:
            lesson = LifeSkillLesson(teacher_id=current_user.id, **data)
            db.session.add(lesson)
            db.session.commit()
            flash('Đã upload bài học kỹ năng sống', 'success')
            return redirect(url_for('teacher_life_skills'))
    return render_template('teacher_life_skill_form.html', lesson=None)


@app.route('/teacher/life-skills/<int:lesson_id>/edit', methods=['GET', 'POST'])
@login_required
def teacher_life_skill_edit(lesson_id):
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    lesson = LifeSkillLesson.query.get_or_404(lesson_id)
    if lesson.teacher_id != current_user.id:
        flash('Bạn chỉ có thể chỉnh sửa bài học của mình', 'danger')
        return redirect(url_for('teacher_life_skills'))
    if request.method == 'POST':
        data = collect_life_skill_lesson_form()
        required = [data['title'], data['skill_category'], data['video_url'], data['description']]
        if not all(required):
            flash('Vui lòng nhập tiêu đề, kỹ năng, link video và mô tả', 'warning')
        else:
            for key, value in data.items():
                setattr(lesson, key, value)
            lesson.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Đã cập nhật bài học kỹ năng sống', 'success')
            return redirect(url_for('teacher_life_skills'))
    return render_template('teacher_life_skill_form.html', lesson=lesson)


@app.route('/student/life-skills')
@login_required
def student_life_skills():
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    lessons = LifeSkillLesson.query.filter_by(is_published=True).order_by(LifeSkillLesson.is_featured.desc(), LifeSkillLesson.updated_at.desc()).all()
    categories = ['Tất cả'] + sorted({lesson.skill_category for lesson in lessons})
    active_category = request.args.get('category', 'Tất cả')
    if active_category != 'Tất cả':
        lessons = [lesson for lesson in lessons if lesson.skill_category == active_category]
    progress_items = LifeSkillProgress.query.filter_by(student_id=current_user.id).all()
    progress_by_lesson = {item.lesson_id: item for item in progress_items}
    return render_template(
        'student_life_skills.html',
        lessons=lessons,
        categories=categories,
        active_category=active_category,
        progress_by_lesson=progress_by_lesson,
        video_platform=video_platform,
    )


@app.route('/student/life-skills/<int:lesson_id>', methods=['GET', 'POST'])
@login_required
def student_life_skill_detail(lesson_id):
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    lesson = LifeSkillLesson.query.filter_by(id=lesson_id, is_published=True).first_or_404()
    progress = LifeSkillProgress.query.filter_by(lesson_id=lesson.id, student_id=current_user.id).first()
    if request.method == 'POST':
        if not progress:
            progress = LifeSkillProgress(lesson_id=lesson.id, student_id=current_user.id)
            db.session.add(progress)
        progress.is_completed = request.form.get('is_completed') == 'on'
        progress.feedback = (request.form.get('feedback') or '').strip()
        progress.reflection = (request.form.get('reflection') or '').strip()
        progress.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Đã lưu tiến độ bài học', 'success')
        return redirect(url_for('student_life_skill_detail', lesson_id=lesson.id))
    return render_template(
        'student_life_skill_detail.html',
        lesson=lesson,
        progress=progress,
        embed_url=video_embed_url(lesson.video_url),
        platform=video_platform(lesson.video_url),
    )


@app.route('/student/profile', methods=['GET', 'POST'])
@login_required
def student_profile():
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    profile = get_or_create_student_profile(current_user.id)
    if request.method == 'POST':
        avatar_file = request.files.get('avatar')
        if avatar_file and avatar_file.filename:
            avatar_filename = save_profile_image(avatar_file, current_user.id)
            if avatar_filename:
                profile.avatar_filename = avatar_filename
            else:
                flash('Ảnh hồ sơ chỉ hỗ trợ PNG, JPG, JPEG hoặc WEBP', 'warning')
                return redirect(url_for('student_profile'))
        profile.full_name = (request.form.get('full_name') or '').strip()
        profile.class_name = (request.form.get('class_name') or '').strip()
        profile.address = (request.form.get('address') or '').strip()
        profile.phone = (request.form.get('phone') or '').strip()
        profile.guardian_name = (request.form.get('guardian_name') or '').strip()
        profile.guardian_phone = (request.form.get('guardian_phone') or '').strip()
        profile.emergency_contact = (request.form.get('emergency_contact') or '').strip()
        profile.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Đã cập nhật hồ sơ học sinh', 'success')
        return redirect(url_for('student_profile'))
    return render_template('student_profile.html', profile=profile)


@app.route('/teacher/profile', methods=['GET', 'POST'])
@login_required
def teacher_profile():
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    profile = get_or_create_teacher_profile(current_user.id)
    if request.method == 'POST':
        avatar_file = request.files.get('avatar')
        if avatar_file and avatar_file.filename:
            avatar_filename = save_profile_image(avatar_file, current_user.id, prefix='teacher')
            if avatar_filename:
                profile.avatar_filename = avatar_filename
            else:
                flash('Ảnh hồ sơ chỉ hỗ trợ PNG, JPG, JPEG hoặc WEBP', 'warning')
                return redirect(url_for('teacher_profile'))
        profile.full_name = (request.form.get('full_name') or '').strip()
        profile.department = (request.form.get('department') or '').strip()
        profile.subject = (request.form.get('subject') or '').strip()
        profile.phone = (request.form.get('phone') or '').strip()
        profile.email_contact = (request.form.get('email_contact') or '').strip()
        profile.office_location = (request.form.get('office_location') or '').strip()
        profile.consultation_time = (request.form.get('consultation_time') or '').strip()
        profile.bio = (request.form.get('bio') or '').strip()
        profile.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Đã cập nhật hồ sơ giáo viên', 'success')
        return redirect(url_for('teacher_profile'))
    return render_template('teacher_profile.html', profile=profile)


@app.route('/student/psychology/chat')
@login_required
def student_chat_rooms():
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    teachers = User.query.filter_by(role='teacher', is_active=True).order_by(User.username).all()
    kbot_conversation = get_or_create_conversation('kbot', current_user.id)
    return render_template('student_chat_rooms.html', teachers=teachers, kbot_conversation=kbot_conversation)


@app.route('/student/psychology/chat/kbot')
@login_required
def student_kbot_chat():
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    conversation = get_or_create_conversation('kbot', current_user.id)
    messages = ChatMessage.query.filter_by(conversation_id=conversation.id).order_by(ChatMessage.created_at.asc()).all()
    return render_template('chat_room.html', conversation=conversation, messages=messages, peer_name='Kbot', mode='kbot')


@app.route('/student/psychology/chat/teacher/<int:teacher_id>')
@login_required
def student_teacher_chat(teacher_id):
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    teacher = User.query.filter_by(id=teacher_id, role='teacher', is_active=True).first_or_404()
    conversation = get_or_create_conversation('teacher', current_user.id, teacher.id)
    messages = ChatMessage.query.filter_by(conversation_id=conversation.id).order_by(ChatMessage.created_at.asc()).all()
    return render_template('chat_room.html', conversation=conversation, messages=messages, peer_name=teacher.username, mode='teacher')


@app.route('/teacher/psychology/messages')
@login_required
def teacher_chat_list():
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    conversations = ChatConversation.query.filter_by(room_type='teacher', teacher_id=current_user.id).order_by(ChatConversation.updated_at.desc()).all()
    student_ids = sorted({conversation.student_id for conversation in conversations})
    students = User.query.filter(User.id.in_(student_ids)).all() if student_ids else []
    students_by_id = {student.id: student for student in students}
    latest_messages = {}
    for conversation in conversations:
        latest_messages[conversation.id] = ChatMessage.query.filter_by(
            conversation_id=conversation.id,
        ).order_by(ChatMessage.created_at.desc()).first()
    return render_template(
        'teacher_chat_list.html',
        conversations=conversations,
        students_by_id=students_by_id,
        latest_messages=latest_messages,
    )


@app.route('/teacher/psychology/messages/<int:conversation_id>')
@login_required
def teacher_chat_room(conversation_id):
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    conversation = ChatConversation.query.get_or_404(conversation_id)
    if not can_access_conversation(conversation):
        flash('Bạn không có quyền xem cuộc trò chuyện này', 'danger')
        return redirect(url_for('teacher_chat_list'))
    student = User.query.get(conversation.student_id)
    messages = ChatMessage.query.filter_by(conversation_id=conversation.id).order_by(ChatMessage.created_at.asc()).all()
    return render_template('chat_room.html', conversation=conversation, messages=messages, peer_name=student.username if student else 'Học sinh', mode='teacher')


@app.route('/parent/teacher-chat')
@login_required
def parent_teacher_chat_list():
    if not role_required('parent'):
        return redirect(url_for('dashboard'))
    teachers = User.query.filter_by(role='teacher', is_active=True).order_by(User.username).all()
    return render_template('parent_teacher_chat_list.html', teachers=teachers)


@app.route('/parent/teacher-chat/<int:teacher_id>')
@login_required
def parent_teacher_chat(teacher_id):
    if not role_required('parent'):
        return redirect(url_for('dashboard'))
    teacher = User.query.filter_by(id=teacher_id, role='teacher', is_active=True).first_or_404()
    conversation = get_or_create_conversation('parent', current_user.id, teacher.id)
    messages = ChatMessage.query.filter_by(conversation_id=conversation.id).order_by(ChatMessage.created_at.asc()).all()
    return render_template(
        'chat_room.html',
        conversation=conversation,
        messages=messages,
        peer_name=teacher.username,
        mode='parent',
        back_url=url_for('dashboard'),
    )


@app.route('/teacher/parent-messages')
@login_required
def teacher_parent_chat_list():
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    conversations = ChatConversation.query.filter_by(room_type='parent', teacher_id=current_user.id).order_by(ChatConversation.updated_at.desc()).all()
    parent_ids = sorted({conversation.student_id for conversation in conversations})
    conversation_parents = User.query.filter(User.id.in_(parent_ids)).all() if parent_ids else []
    parents_by_id = {parent.id: parent for parent in conversation_parents}
    all_parents = User.query.filter_by(role='parent', is_active=True).order_by(User.username.asc()).all()
    conversations_by_parent = {conversation.student_id: conversation for conversation in conversations}
    latest_messages = {}
    for conversation in conversations:
        latest_messages[conversation.id] = ChatMessage.query.filter_by(
            conversation_id=conversation.id,
        ).order_by(ChatMessage.created_at.desc()).first()
    return render_template(
        'teacher_parent_chat_list.html',
        conversations=conversations,
        parents_by_id=parents_by_id,
        all_parents=all_parents,
        conversations_by_parent=conversations_by_parent,
        latest_messages=latest_messages,
    )


@app.route('/teacher/parent-messages/start/<int:parent_id>')
@login_required
def teacher_parent_chat_start(parent_id):
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    parent = User.query.filter_by(id=parent_id, role='parent', is_active=True).first_or_404()
    conversation = get_or_create_conversation('parent', parent.id, current_user.id)
    return redirect(url_for('teacher_parent_chat_room', conversation_id=conversation.id))


@app.route('/teacher/parent-messages/<int:conversation_id>')
@login_required
def teacher_parent_chat_room(conversation_id):
    if not role_required('teacher'):
        return redirect(url_for('dashboard'))
    conversation = ChatConversation.query.filter_by(id=conversation_id, room_type='parent').first_or_404()
    if not can_access_conversation(conversation):
        flash('Bạn không có quyền xem cuộc trò chuyện này', 'danger')
        return redirect(url_for('teacher_parent_chat_list'))
    parent = User.query.get(conversation.student_id)
    messages = ChatMessage.query.filter_by(conversation_id=conversation.id).order_by(ChatMessage.created_at.asc()).all()
    return render_template(
        'chat_room.html',
        conversation=conversation,
        messages=messages,
        peer_name=parent.username if parent else 'Phụ huynh',
        mode='parent',
        back_url=url_for('teacher_parent_chat_list'),
    )


@app.route('/student/psychology/emotion-journal', methods=['GET', 'POST'])
@login_required
def emotion_journal():
    if not role_required('student'):
        return redirect(url_for('dashboard'))
    prompt = daily_emotion_prompt()
    if request.method == 'POST':
        mood = (request.form.get('mood') or '').strip()
        intensity = request.form.get('intensity', type=int)
        triggers = request.form.getlist('triggers')
        note = (request.form.get('note') or '').strip()
        if not mood or not intensity or intensity < 1 or intensity > 5:
            flash('Vui lòng chọn cảm xúc và mức độ 1–5', 'warning')
        else:
            entry = EmotionEntry(
                student_id=current_user.id,
                mood=mood,
                intensity=intensity,
                triggers_json=json.dumps(triggers, ensure_ascii=False),
                note=note,
                prompt=prompt,
            )
            db.session.add(entry)
            db.session.commit()
            flash('Đã lưu nhật ký cảm xúc hôm nay', 'success')
            return redirect(url_for('emotion_journal'))
    entries = emotion_weekly_entries(current_user.id)
    recent_entries = recent_emotion_entries(current_user.id)
    moment_label = datetime.now().strftime('%d/%m/%Y')
    return render_template(
        'emotion_journal.html',
        prompt=prompt,
        entries=entries,
        recent_entries=recent_entries,
        moment_label=moment_label,
    )


if socketio:
    @socketio.on('join_chat')
    def handle_join_chat(data):
        conversation = ChatConversation.query.get(data.get('conversation_id'))
        if not conversation or not current_user.is_authenticated or not can_access_conversation(conversation):
            return
        join_room(conversation_room(conversation.id))

    @socketio.on('send_chat_message')
    def handle_send_chat_message(data):
        conversation = ChatConversation.query.get(data.get('conversation_id'))
        content = (data.get('content') or '').strip()
        if not conversation or not content or not current_user.is_authenticated or not can_access_conversation(conversation):
            return
        message = save_chat_message(conversation.id, current_user.id, current_user.role, content)
        emit('chat_message', serialize_chat_message(message), room=conversation_room(conversation.id))
        if conversation.room_type == 'kbot' and current_user.role == 'student':
            reply_text = ask_kbot(content)
            reply = save_chat_message(conversation.id, None, 'kbot', reply_text)
            emit('chat_message', serialize_chat_message(reply), room=conversation_room(conversation.id))


@app.route('/chat/api/<int:conversation_id>/messages')
@login_required
def chat_api_messages(conversation_id):
    conversation = ChatConversation.query.get_or_404(conversation_id)
    if not can_access_conversation(conversation):
        return {'error': 'forbidden'}, 403
    after_id = request.args.get('after_id', type=int) or 0
    messages = ChatMessage.query.filter(
        ChatMessage.conversation_id == conversation.id,
        ChatMessage.id > after_id,
    ).order_by(ChatMessage.id.asc()).all()
    return {'messages': [serialize_chat_message(message) for message in messages]}


@app.route('/chat/api/<int:conversation_id>/messages', methods=['POST'])
@login_required
@csrf.exempt
def chat_api_send_message(conversation_id):
    conversation = ChatConversation.query.get_or_404(conversation_id)
    if not can_access_conversation(conversation):
        return {'error': 'forbidden'}, 403
    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    if not content:
        return {'error': 'empty'}, 400
    message = save_chat_message(conversation.id, current_user.id, current_user.role, content)
    response_messages = [serialize_chat_message(message)]
    if socketio:
        socketio.emit('chat_message', response_messages[0], room=conversation_room(conversation.id))
    if conversation.room_type == 'kbot' and current_user.role == 'student':
        reply_text = ask_kbot(content)
        reply = save_chat_message(conversation.id, None, 'kbot', reply_text)
        serialized_reply = serialize_chat_message(reply)
        response_messages.append(serialized_reply)
        if socketio:
            socketio.emit('chat_message', serialized_reply, room=conversation_room(conversation.id))
    return {'messages': response_messages}


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Đã đăng xuất', 'info')
    return redirect(url_for('login'))


def initialize_database():
    with app.app_context():
        db.create_all()


initialize_database()


if __name__ == '__main__':
    if socketio:
        socketio.run(app, debug=True)
    else:
        app.run(debug=True)
