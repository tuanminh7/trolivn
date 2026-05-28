import json
from datetime import datetime, timedelta

from app import (
    app,
    db,
    User,
    Message,
    PsychologyTopic,
    PsychologyQuestion,
    PsychologySubmission,
    ChatConversation,
    ChatMessage,
    EmotionEntry,
    StudentProfile,
    CareerTest,
    CareerQuestion,
    CareerSubmission,
    CareerJob,
    CareerInquiry,
    CareerLearningPath,
    ForumPost,
    ForumReaction,
    ForumComment,
    LifeSkillLesson,
    replace_learning_path_details,
)


def get_or_create_user(username, email, password, role):
    user = User.query.filter_by(email=email).first()
    if user:
        if not user.account_id:
            user.account_id = User.next_account_id()
        user.is_active = True
        return user
    user = User(username=username, email=email, role=role, is_active=True)
    user.account_id = User.next_account_id()
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user


def seed_users():
    users = {
        'admin': get_or_create_user('adminuser', 'admin@example.com', 'adminpass', 'admin'),
        'teacher': get_or_create_user('teacher1', 'teacher@example.com', 'teacherpass', 'teacher'),
        'student': get_or_create_user('student1', 'student@example.com', 'studentpass', 'student'),
        'parent': get_or_create_user('parent1', 'parent@example.com', 'parentpass', 'parent'),
    }
    db.session.commit()
    return users


def seed_student_profile(student):
    profile = StudentProfile.query.filter_by(student_id=student.id).first()
    if not profile:
        profile = StudentProfile(student_id=student.id)
        db.session.add(profile)
    profile.full_name = profile.full_name or 'Nguyễn Minh An'
    profile.class_name = profile.class_name or '10A1'
    profile.address = profile.address or 'Quận 1, TP. Hồ Chí Minh'
    profile.phone = profile.phone or '0901002003'
    profile.guardian_name = profile.guardian_name or 'Nguyễn Thị Mai'
    profile.guardian_phone = profile.guardian_phone or '0903004005'
    profile.emergency_contact = profile.emergency_contact or 'Cô Mai - 0903004005'


def seed_psychology(teacher, student):
    topic = PsychologyTopic.query.filter_by(title='Đánh giá căng thẳng học tập', teacher_id=teacher.id).first()
    if not topic:
        topic = PsychologyTopic(
            title='Đánh giá căng thẳng học tập',
            description='Bài trắc nghiệm ngắn giúp học sinh tự nhìn lại mức độ căng thẳng khi học.',
            teacher_id=teacher.id,
            is_published=True,
        )
        db.session.add(topic)
        db.session.flush()
    if PsychologyQuestion.query.filter_by(topic_id=topic.id).count() == 0:
        questions = [
            ('Khi gần đến hạn kiểm tra, bạn thường cảm thấy thế nào?', 'Bình tĩnh', 'Hơi lo', 'Khá căng', 'Rất áp lực'),
            ('Bạn có dễ mất tập trung khi học không?', 'Hiếm khi', 'Thỉnh thoảng', 'Khá thường xuyên', 'Gần như luôn luôn'),
            ('Sau giờ học, bạn có thấy mệt mỏi kéo dài không?', 'Không', 'Ít', 'Nhiều', 'Rất nhiều'),
            ('Bạn có ngủ đủ trước ngày kiểm tra không?', 'Đủ', 'Thiếu nhẹ', 'Thiếu nhiều', 'Gần như mất ngủ'),
            ('Khi gặp bài khó, bạn thường phản ứng ra sao?', 'Tìm cách giải', 'Hỏi bạn/thầy cô', 'Bối rối', 'Muốn bỏ cuộc'),
        ]
        for index, question in enumerate(questions, start=1):
            db.session.add(PsychologyQuestion(
                topic_id=topic.id,
                question_text=question[0],
                option_a=question[1],
                option_b=question[2],
                option_c=question[3],
                option_d=question[4],
                position=index,
            ))
    if not PsychologySubmission.query.filter_by(topic_id=topic.id, student_id=student.id).first():
        db.session.add(PsychologySubmission(
            topic_id=topic.id,
            student_id=student.id,
            score=7,
            percent=47,
            level=3,
            answers_json=json.dumps({'demo': 'seed'}),
            created_at=datetime.utcnow() - timedelta(days=1),
        ))


def seed_emotions(student):
    if EmotionEntry.query.filter_by(student_id=student.id).count() >= 7:
        return
    data = [
        ('vui', 4, ['Bạn bè'], 'Hôm nay nói chuyện với bạn thân thấy nhẹ lòng hơn.'),
        ('binh_than', 3, ['Bản thân'], 'Tự học được một chút nên thấy ổn.'),
        ('cang_thang', 4, ['Học tập'], 'Tối thứ Tư hơi căng vì bài kiểm tra gần tới.'),
        ('lo_lang', 3, ['Gia đình', 'Học tập'], 'Mình lo bố mẹ chưa hiểu ngành mình thích.'),
        ('vui', 5, ['Bạn bè'], 'Được bạn rủ học nhóm, vui hơn nhiều.'),
        ('buon', 2, ['Khác'], 'Có lúc thấy hơi trống rỗng dù xung quanh đông người.'),
        ('binh_than', 3, ['Sức khỏe'], 'Ngủ đủ nên tâm trạng ổn hơn.'),
    ]
    for offset, item in enumerate(data):
        db.session.add(EmotionEntry(
            student_id=student.id,
            mood=item[0],
            intensity=item[1],
            triggers_json=json.dumps(item[2], ensure_ascii=False),
            note=item[3],
            prompt='Hôm nay điều gì khiến bạn mỉm cười?',
            created_at=datetime.utcnow() - timedelta(days=6 - offset),
        ))


def seed_chat_and_admin_messages(admin, teacher, student):
    if not Message.query.filter_by(sender_id=student.id, recipient_id=admin.id, content='Em cần hỗ trợ về tài khoản và lịch tư vấn.').first():
        message = Message(
            sender_id=student.id,
            recipient_id=admin.id,
            content='Em cần hỗ trợ về tài khoản và lịch tư vấn.',
            created_at=datetime.utcnow() - timedelta(hours=6),
        )
        db.session.add(message)
        db.session.flush()
        db.session.add(Message(
            sender_id=admin.id,
            recipient_id=student.id,
            content='Admin đã nhận thông tin, em kiểm tra hộp thư và phản hồi nếu cần thêm hỗ trợ nhé.',
            reply_to=message.id,
            created_at=datetime.utcnow() - timedelta(hours=5),
        ))

    conversation = ChatConversation.query.filter_by(room_type='teacher', student_id=student.id, teacher_id=teacher.id).first()
    if not conversation:
        conversation = ChatConversation(room_type='teacher', student_id=student.id, teacher_id=teacher.id)
        db.session.add(conversation)
        db.session.flush()
    if ChatMessage.query.filter_by(conversation_id=conversation.id).count() == 0:
        db.session.add(ChatMessage(conversation_id=conversation.id, sender_id=student.id, sender_role='student', content='Em muốn hỏi về cách giảm áp lực học tập.'))
        db.session.add(ChatMessage(conversation_id=conversation.id, sender_id=teacher.id, sender_role='teacher', content='Cô ở đây. Em thử chia nhỏ việc học thành từng phiên 25 phút trước nhé.'))


def seed_career_tests(teacher, student):
    tests = [
        ('Phong cách học tập', 'Tìm hiểu cách học phù hợp với bạn.'),
        ('Cách xử lý cảm xúc', 'Nhìn lại cách bạn phản ứng khi gặp áp lực.'),
        ('Kiểu kết bạn', 'Khám phá cách bạn kết nối với bạn bè.'),
    ]
    for title, description in tests:
        test = CareerTest.query.filter_by(title=title, teacher_id=teacher.id).first()
        if not test:
            test = CareerTest(title=title, description=description, teacher_id=teacher.id, is_published=True)
            db.session.add(test)
            db.session.flush()
        if CareerQuestion.query.filter_by(test_id=test.id).count() == 0:
            for index in range(1, 6):
                db.session.add(CareerQuestion(
                    test_id=test.id,
                    question_text=f'Câu {index}: Bạn thấy lựa chọn nào giống mình nhất?',
                    image_url='',
                    option_a='Thích tự tìm hiểu trước',
                    option_b='Thích trao đổi với bạn bè',
                    option_c='Thích có ví dụ trực quan',
                    option_d='Thích được hướng dẫn từng bước',
                    position=index,
                ))
        if title == 'Phong cách học tập' and not CareerSubmission.query.filter_by(test_id=test.id, student_id=student.id).first():
            db.session.add(CareerSubmission(
                test_id=test.id,
                student_id=student.id,
                score=15,
                percent=75,
                answers_json=json.dumps({'demo': 'seed'}),
            ))


def seed_career_jobs_and_inquiry(teacher, student):
    jobs = [
        ('Lập trình viên', 'Công nghệ', '</>', 'Xây dựng phần mềm, ứng dụng và hệ thống', ['Logic', 'Sáng tạo'], 'Viết, kiểm tra và duy trì mã nguồn để xây dựng phần mềm, ứng dụng web/di động và hệ thống tự động hóa.', '4 năm', '9–25tr', 'Cao', 'Tư duy logic, kiên nhẫn giải quyết vấn đề, học liên tục và khả năng làm việc độc lập.', 'purple', True),
        ('Bác sĩ', 'Y tế', '♧', 'Chăm sóc sức khỏe và điều trị bệnh', ['Khoa học', 'Tỉ mỉ'], 'Khám, chẩn đoán, tư vấn và theo dõi sức khỏe cho người bệnh.', '6–9 năm', '12–40tr', 'Ổn định', 'Cẩn thận, đồng cảm, chịu áp lực tốt và yêu thích khoa học sự sống.', 'green', True),
        ('Thiết kế đồ họa', 'Sáng tạo', '◒', 'Tạo hình ảnh, nhận diện và sản phẩm truyền thông', ['Thẩm mỹ', 'Sáng tạo'], 'Thiết kế poster, logo, giao diện và ấn phẩm truyền thông cho thương hiệu.', '2–4 năm', '8–22tr', 'Khá', 'Có gu thẩm mỹ, thích quan sát, chịu khó chỉnh sửa và kể chuyện bằng hình ảnh.', 'yellow', True),
        ('Data analyst', 'Kinh doanh', '▥', 'Phân tích dữ liệu để hỗ trợ quyết định kinh doanh', ['Dữ liệu', 'Kinh doanh'], 'Thu thập, làm sạch, trực quan hóa dữ liệu và rút ra insight cho đội nhóm.', '3–4 năm', '10–28tr', 'Cao', 'Tò mò, thích con số, kiên nhẫn kiểm chứng và biết đặt câu hỏi đúng.', 'green', False),
        ('Nhà báo / Content creator', 'Sáng tạo', '♬', 'Sản xuất nội dung, kể chuyện và truyền thông', ['Sáng tạo', 'Ngôn ngữ'], 'Tìm ý tưởng, viết kịch bản/bài viết, phỏng vấn và sản xuất nội dung đa nền tảng.', '3–4 năm', '7–25tr', 'Linh hoạt', 'Giao tiếp tốt, nhạy với xu hướng, thích kể chuyện và có kỷ luật nội dung.', 'yellow', False),
        ('Chuyên viên tâm lý', 'Xã hội', '✚', 'Hỗ trợ sức khỏe tinh thần và tư vấn cá nhân', ['Lắng nghe', 'Đồng cảm'], 'Lắng nghe, đánh giá nhu cầu hỗ trợ và đồng hành cùng cá nhân/nhóm trong vấn đề tinh thần.', '4–6 năm', '8–24tr', 'Đang tăng', 'Điềm tĩnh, biết lắng nghe, bảo mật tốt và có mong muốn giúp người khác.', 'orange', False),
    ]
    first_job = None
    for item in jobs:
        job = CareerJob.query.filter_by(name=item[0], teacher_id=teacher.id).first()
        if not job:
            job = CareerJob(
                teacher_id=teacher.id,
                name=item[0],
                field=item[1],
                icon=item[2],
                summary=item[3],
                skills_json=json.dumps(item[4], ensure_ascii=False),
                work=item[5],
                study=item[6],
                salary=item[7],
                demand=item[8],
                personality=item[9],
                color=item[10],
                is_featured=item[11],
                is_published=True,
            )
            db.session.add(job)
            db.session.flush()
        if not first_job:
            first_job = job
    if first_job and not CareerInquiry.query.filter_by(job_id=first_job.id, student_id=student.id).first():
        db.session.add(CareerInquiry(
            job_id=first_job.id,
            student_id=student.id,
            teacher_id=teacher.id,
            question='Nghề này cần học môn nào nhiều nhất ạ?',
            reply='Em nên tập trung Toán, Tin học và kỹ năng tự học. Nếu thích sản phẩm trực quan, có thể thử làm website nhỏ trước.',
            replied_at=datetime.utcnow(),
        ))


def seed_forum(student):
    posts = [
        ('Học tập', 'Làm sao để tập trung học khi đầu óc cứ nghĩ lung tung?', 'Mình hay bị mất tập trung sau 20 phút, đặc biệt khi học môn không thích. Các bạn có mẹo gì không?', False),
        ('Cảm xúc', 'Mình cảm thấy cô đơn dù xung quanh có nhiều bạn bè', 'Không biết giải thích thế nào, đôi khi ở giữa đám đông mà vẫn thấy trống rỗng. Có ai từng có cảm giác này không?', True),
        ('Hướng nghiệp', 'Mình muốn theo ngành thiết kế nhưng bố mẹ muốn mình học kinh tế', 'Áp lực quá, không biết nên nghe theo bố mẹ hay theo đuổi điều mình thích. Các bạn đã từng đối mặt với tình huống này chưa?', False),
    ]
    created_posts = []
    for category, title, content, anonymous in posts:
        post = ForumPost.query.filter_by(title=title, student_id=student.id).first()
        if not post:
            post = ForumPost(student_id=student.id, category=category, title=title, content=content, is_anonymous=anonymous)
            db.session.add(post)
            db.session.flush()
        created_posts.append(post)
    for post in created_posts:
        if not ForumReaction.query.filter_by(post_id=post.id, student_id=student.id).first():
            db.session.add(ForumReaction(post_id=post.id, student_id=student.id, reaction_type='empathy'))
        if ForumComment.query.filter_by(post_id=post.id).count() == 0:
            db.session.add(ForumComment(post_id=post.id, student_id=student.id, content='Mình cũng từng như vậy, cảm ơn bạn đã chia sẻ.', is_anonymous=True))


def build_learning_payload(career_name, focus_subject, practice_task, skill_names):
    stages = [
        {
            'year_label': 'Lớp 10',
            'subtitle': '',
            'title': 'Xây nền tảng',
            'status': 'Chưa hoàn thành',
            'is_open': True,
            'tasks': [
                {'title': f'Học tốt {focus_subject}', 'subtitle': f'Môn học nền tảng cho {career_name}', 'type': 'Môn học', 'done': False},
                {'title': 'Rèn thói quen tự học', 'subtitle': 'Ghi chú, đặt mục tiêu tuần, tự đánh giá', 'type': 'Kỹ năng', 'done': False},
                {'title': practice_task, 'subtitle': 'Dự án nhỏ để hiểu nghề thực tế', 'type': 'Thực hành', 'done': False},
            ],
        },
        {
            'year_label': 'Lớp 11',
            'subtitle': 'Đang học',
            'title': 'Phát triển kỹ năng',
            'status': 'Đang làm',
            'is_open': True,
            'tasks': [
                {'title': f'Học chuyên sâu về {career_name}', 'subtitle': 'Tài liệu cơ bản, khóa học ngắn, bài tập thực hành', 'type': 'Kỹ năng', 'done': False},
                {'title': f'Duy trì điểm tốt ở {focus_subject}', 'subtitle': 'Chuẩn bị nền tảng xét tuyển', 'type': 'Môn học', 'done': False},
                {'title': 'Làm 1 sản phẩm hoàn chỉnh', 'subtitle': 'Có thể đưa vào portfolio cá nhân', 'type': 'Thực hành', 'done': False},
                {'title': 'Tham gia CLB hoặc hoạt động liên quan', 'subtitle': 'Trải nghiệm làm việc nhóm', 'type': 'Hoạt động', 'done': False},
            ],
        },
        {
            'year_label': 'Lớp 12',
            'subtitle': '',
            'title': 'Chuẩn bị thi & hồ sơ',
            'status': 'Sắp tới',
            'is_open': False,
            'tasks': [
                {'title': 'Chọn tổ hợp xét tuyển phù hợp', 'subtitle': 'So sánh trường, ngành và điều kiện đầu vào', 'type': 'Môn học', 'done': False},
                {'title': 'Hoàn thiện portfolio/hồ sơ', 'subtitle': 'Lưu lại sản phẩm, chứng chỉ và hoạt động nổi bật', 'type': 'Thực hành', 'done': False},
            ],
        },
        {
            'year_label': 'Đại học',
            'subtitle': '',
            'title': 'Chuyên sâu & thực tập',
            'status': 'Tương lai',
            'is_open': False,
            'tasks': [
                {'title': 'Học kiến thức chuyên ngành', 'subtitle': 'Xây nền tảng nghề nghiệp dài hạn', 'type': 'Kỹ năng', 'done': False},
                {'title': 'Tìm thực tập hoặc dự án thực tế', 'subtitle': 'Làm quen môi trường nghề nghiệp', 'type': 'Hoạt động', 'done': False},
            ],
        },
    ]
    skills = [
        {'name': skill_names[0], 'level': 'Trung cấp', 'percent': 60, 'color': 'purple'},
        {'name': skill_names[1], 'level': 'Khá tốt', 'percent': 75, 'color': 'green'},
        {'name': 'Tiếng Anh', 'level': 'Cơ bản', 'percent': 45, 'color': 'yellow'},
        {'name': 'Làm việc nhóm', 'level': 'Đang rèn', 'percent': 40, 'color': 'pink'},
    ]
    return stages, skills


def seed_learning_paths(teacher):
    careers = [
        ('Lập trình viên', 'Phát triển phần mềm, web, ứng dụng di động', '</>', 'purple', 'Toán, Tin học', 'Viết một website cá nhân đơn giản', ['Lập trình Python', 'Toán tư duy']),
        ('Thiết kế UX/UI', 'Thiết kế trải nghiệm người dùng và giao diện sản phẩm', '◎', 'pink', 'Mỹ thuật, Tin học', 'Thiết kế lại giao diện một app quen thuộc', ['Tư duy thiết kế', 'Quan sát người dùng']),
        ('Khoa học dữ liệu', 'Phân tích dữ liệu, AI, machine learning', '⌁', 'green', 'Toán, Tin học', 'Phân tích một bảng dữ liệu nhỏ', ['Phân tích dữ liệu', 'Toán thống kê']),
        ('Kinh doanh', 'Marketing, quản trị, khởi nghiệp', '▣', 'yellow', 'Toán, Ngữ văn, Tiếng Anh', 'Lập kế hoạch bán một sản phẩm nhỏ', ['Tư duy kinh doanh', 'Giao tiếp']),
        ('Y tế', 'Bác sĩ, dược sĩ, điều dưỡng', '♧', 'orange', 'Sinh học, Hóa học', 'Tìm hiểu một chủ đề sức khỏe cộng đồng', ['Sinh học ứng dụng', 'Đồng cảm']),
        ('Giáo dục', 'Giảng dạy, nghiên cứu, huấn luyện', '◈', 'blue', 'Ngữ văn, Tiếng Anh', 'Soạn một bài hướng dẫn ngắn cho bạn bè', ['Truyền đạt', 'Kiên nhẫn']),
        ('Truyền thông', 'Sản xuất nội dung, báo chí, quan hệ công chúng', '♬', 'yellow', 'Ngữ văn, Tiếng Anh', 'Làm một bài viết hoặc video ngắn', ['Viết nội dung', 'Kể chuyện']),
        ('Tâm lý học', 'Tham vấn, nghiên cứu hành vi, hỗ trợ tinh thần', '✚', 'green', 'Ngữ văn, Sinh học', 'Đọc và tóm tắt một chủ đề tâm lý học đường', ['Lắng nghe', 'Quan sát cảm xúc']),
        ('Kỹ thuật cơ khí', 'Thiết kế, chế tạo, vận hành máy móc', '⚙', 'blue', 'Toán, Vật lý', 'Làm mô hình kỹ thuật nhỏ', ['Tư duy kỹ thuật', 'Vật lý ứng dụng']),
        ('Du lịch khách sạn', 'Dịch vụ, lữ hành, quản trị trải nghiệm khách hàng', '✈', 'orange', 'Tiếng Anh, Địa lý', 'Lập kế hoạch tour một ngày', ['Dịch vụ khách hàng', 'Ngoại ngữ']),
    ]
    for title, summary, icon, color, subject, practice, skills in careers:
        path = CareerLearningPath.query.filter_by(title=title, teacher_id=teacher.id).first()
        stages, skill_data = build_learning_payload(title, subject, practice, skills)
        if not path:
            path = CareerLearningPath(
                teacher_id=teacher.id,
                title=title,
                summary=summary,
                icon=icon,
                color=color,
                goal_label=title,
                completion_percent=0,
                is_published=True,
            )
            db.session.add(path)
            db.session.flush()
            replace_learning_path_details(path, stages, skill_data)
        elif not path.is_published:
            path.is_published = True


def seed_life_skills(teacher):
    lessons = [
        {
            'title': 'Lắng nghe chủ động khi trò chuyện',
            'skill_category': 'Giao tiếp',
            'video_url': 'https://www.youtube.com/watch?v=H14bBuluwB8',
            'thumbnail_url': 'https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=900&q=80',
            'duration': '8 phút',
            'description': 'Học cách nhìn vào người nói, đặt câu hỏi lại và phản hồi bằng thái độ tôn trọng.',
            'practice_steps': 'Chọn một bạn để trò chuyện trong 5 phút.\nKhông ngắt lời khi bạn đang nói.\nTóm tắt lại điều bạn nghe được bằng một câu ngắn.',
            'reflection_question': 'Hôm nay em đã lắng nghe ai tốt hơn bình thường?',
            'is_featured': True,
        },
        {
            'title': 'Bình tĩnh khi bị áp lực kiểm tra',
            'skill_category': 'Quản lý cảm xúc',
            'video_url': 'https://www.youtube.com/watch?v=inpok4MKVLM',
            'thumbnail_url': 'https://images.unsplash.com/photo-1503676260728-1c00da094a0b?auto=format&fit=crop&w=900&q=80',
            'duration': '6 phút',
            'description': 'Thực hành hít thở chậm và chia nhỏ việc học để giảm căng thẳng trước giờ kiểm tra.',
            'practice_steps': 'Hít vào 4 nhịp, giữ 2 nhịp, thở ra 6 nhịp.\nViết ra 3 việc nhỏ cần làm trước khi học.\nNghỉ 5 phút sau mỗi phiên học 25 phút.',
            'reflection_question': 'Khi căng thẳng, cách nào giúp em bình tĩnh nhanh nhất?',
            'is_featured': True,
        },
        {
            'title': 'Lập kế hoạch tự học trong tuần',
            'skill_category': 'Tự học',
            'video_url': 'https://www.youtube.com/watch?v=IlU-zDU6aQ0',
            'thumbnail_url': 'https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=900&q=80',
            'duration': '10 phút',
            'description': 'Biết đặt mục tiêu nhỏ, chọn thời gian học phù hợp và theo dõi tiến độ mỗi ngày.',
            'practice_steps': 'Chọn 1 môn cần cải thiện trong tuần này.\nĐặt 3 mục tiêu nhỏ có thể hoàn thành.\nCuối ngày đánh dấu việc đã làm được.',
            'reflection_question': 'Một mục tiêu nhỏ em muốn hoàn thành trong tuần này là gì?',
            'is_featured': False,
        },
        {
            'title': 'Ứng xử an toàn trên mạng xã hội',
            'skill_category': 'An toàn mạng',
            'video_url': 'https://www.tiktok.com/@school/video/7350000000000000000',
            'thumbnail_url': 'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=900&q=80',
            'duration': '5 phút',
            'description': 'Nhận biết thông tin cần giữ riêng tư và cách phản ứng khi gặp bình luận tiêu cực.',
            'practice_steps': 'Kiểm tra lại thông tin cá nhân đang công khai.\nKhông gửi mật khẩu hoặc mã xác minh cho người khác.\nBáo cho người lớn tin cậy nếu bị đe dọa hoặc bắt nạt.',
            'reflection_question': 'Em muốn thay đổi thói quen nào khi dùng mạng xã hội?',
            'is_featured': False,
        },
        {
            'title': 'Giải quyết mâu thuẫn với bạn bè',
            'skill_category': 'Làm việc nhóm',
            'video_url': 'https://www.youtube.com/watch?v=Q80bs6r9j5E',
            'thumbnail_url': 'https://images.unsplash.com/photo-1517486808906-6ca8b3f04846?auto=format&fit=crop&w=900&q=80',
            'duration': '7 phút',
            'description': 'Dùng câu nói bắt đầu bằng “mình cảm thấy...” để trao đổi nhẹ nhàng khi có hiểu lầm.',
            'practice_steps': 'Viết ra điều em đang khó chịu bằng một câu ngắn.\nĐổi câu trách móc thành câu nói về cảm xúc của mình.\nĐề xuất một việc hai bên có thể cùng thử.',
            'reflection_question': 'Lần tới khi có mâu thuẫn, em muốn nói câu gì trước?',
            'is_featured': False,
        },
    ]
    for data in lessons:
        lesson = LifeSkillLesson.query.filter_by(title=data['title'], teacher_id=teacher.id).first()
        if not lesson:
            lesson = LifeSkillLesson(teacher_id=teacher.id, is_published=True, **data)
            db.session.add(lesson)
        else:
            for key, value in data.items():
                setattr(lesson, key, value)
            lesson.is_published = True


def main():
    with app.app_context():
        db.create_all()
        users = seed_users()
        seed_student_profile(users['student'])
        seed_psychology(users['teacher'], users['student'])
        seed_emotions(users['student'])
        seed_chat_and_admin_messages(users['admin'], users['teacher'], users['student'])
        seed_career_tests(users['teacher'], users['student'])
        seed_career_jobs_and_inquiry(users['teacher'], users['student'])
        seed_learning_paths(users['teacher'])
        seed_forum(users['student'])
        seed_life_skills(users['teacher'])
        db.session.commit()
        print('Seed demo data completed.')
        print('Accounts:')
        for key, user in users.items():
            print(f"- {key}: {user.email} / account_id={user.account_id}")


if __name__ == '__main__':
    main()
