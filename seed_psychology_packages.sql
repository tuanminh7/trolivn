BEGIN;

INSERT INTO psychology_topic (title, description, teacher_id, is_published, created_at, updated_at)
SELECT
  'Khám phá phong cách cảm xúc',
  'Gói 10 câu giúp học sinh nhận diện cách mình phản ứng, điều hòa và chia sẻ cảm xúc trong đời sống học đường.',
  teacher.id,
  1,
  datetime('now'),
  datetime('now')
FROM (SELECT id FROM user WHERE role = 'teacher' ORDER BY id LIMIT 1) AS teacher
WHERE NOT EXISTS (
  SELECT 1 FROM psychology_topic
  WHERE title = 'Khám phá phong cách cảm xúc' AND teacher_id = teacher.id
);

DELETE FROM psychology_question
WHERE topic_id = (
  SELECT psychology_topic.id
  FROM psychology_topic
  JOIN (SELECT id FROM user WHERE role = 'teacher' ORDER BY id LIMIT 1) AS teacher ON teacher.id = psychology_topic.teacher_id
  WHERE psychology_topic.title = 'Khám phá phong cách cảm xúc'
  LIMIT 1
);

INSERT INTO psychology_question (topic_id, question_text, option_a, option_b, option_c, option_d, position)
SELECT topic.id, question_text, option_a, option_b, option_c, option_d, position
FROM (
  SELECT id FROM psychology_topic
  WHERE title = 'Khám phá phong cách cảm xúc'
    AND teacher_id = (SELECT id FROM user WHERE role = 'teacher' ORDER BY id LIMIT 1)
  LIMIT 1
) AS topic
JOIN (
  SELECT 1 AS position, 'Khi gặp chuyện buồn ở lớp, bạn thường phản ứng thế nào?' AS question_text, 'Bình tĩnh nhìn lại vấn đề' AS option_a, 'Tâm sự với người tin cậy' AS option_b, 'Giữ trong lòng khá lâu' AS option_c, 'Dễ cáu hoặc bật khóc' AS option_d
  UNION ALL SELECT 2, 'Khi bị góp ý, bạn cảm thấy thế nào?', 'Lắng nghe và điều chỉnh', 'Hơi buồn nhưng vẫn tiếp nhận', 'Tự trách bản thân nhiều', 'Phản ứng mạnh vì thấy bị chê'
  UNION ALL SELECT 3, 'Bạn có dễ gọi tên cảm xúc của mình không?', 'Rất dễ nhận ra', 'Nhận ra sau một lúc', 'Thường hơi mơ hồ', 'Khó biết mình đang cảm thấy gì'
  UNION ALL SELECT 4, 'Khi căng thẳng, bạn thường làm gì để bình ổn?', 'Hít thở/nghỉ ngơi ngắn', 'Nghe nhạc hoặc viết ra', 'Lướt điện thoại để quên đi', 'Không biết làm gì nên để cảm xúc kéo dài'
  UNION ALL SELECT 5, 'Bạn chia sẻ cảm xúc với bạn bè ở mức nào?', 'Thoải mái khi cần', 'Chỉ chia sẻ với bạn thân', 'Ít chia sẻ vì ngại', 'Hầu như không nói ra'
  UNION ALL SELECT 6, 'Khi mâu thuẫn với bạn, bạn thường chọn cách nào?', 'Nói chuyện rõ ràng', 'Chờ bình tĩnh rồi mới nói', 'Im lặng né tránh', 'Nói ngay lúc đang bực'
  UNION ALL SELECT 7, 'Một ngày không như ý thường ảnh hưởng bạn bao lâu?', 'Một lúc là ổn lại', 'Vài giờ', 'Gần cả ngày', 'Kéo dài sang hôm sau'
  UNION ALL SELECT 8, 'Bạn có nhận ra điều gì thường làm mình vui hơn không?', 'Nhận ra khá rõ', 'Nhận ra một phần', 'Ít để ý', 'Hầu như không biết'
  UNION ALL SELECT 9, 'Khi người khác buồn, bạn thường làm gì?', 'Lắng nghe và ở cạnh', 'Hỏi xem họ cần gì', 'Muốn giúp nhưng hơi lúng túng', 'Tránh vì sợ nói sai'
  UNION ALL SELECT 10, 'Bạn đánh giá khả năng tự chăm sóc cảm xúc của mình hiện tại ra sao?', 'Khá tốt', 'Tạm ổn', 'Cần cải thiện', 'Đang gặp nhiều khó khăn'
) AS questions;

INSERT INTO psychology_topic (title, description, teacher_id, is_published, created_at, updated_at)
SELECT
  'Sức khỏe tinh thần và áp lực học đường',
  'Gói 20 câu giúp học sinh tự nhìn lại áp lực học tập, giấc ngủ, sự tập trung, kết nối xã hội và nhu cầu hỗ trợ.',
  teacher.id,
  1,
  datetime('now'),
  datetime('now')
FROM (SELECT id FROM user WHERE role = 'teacher' ORDER BY id LIMIT 1) AS teacher
WHERE NOT EXISTS (
  SELECT 1 FROM psychology_topic
  WHERE title = 'Sức khỏe tinh thần và áp lực học đường' AND teacher_id = teacher.id
);

DELETE FROM psychology_question
WHERE topic_id = (
  SELECT psychology_topic.id
  FROM psychology_topic
  JOIN (SELECT id FROM user WHERE role = 'teacher' ORDER BY id LIMIT 1) AS teacher ON teacher.id = psychology_topic.teacher_id
  WHERE psychology_topic.title = 'Sức khỏe tinh thần và áp lực học đường'
  LIMIT 1
);

INSERT INTO psychology_question (topic_id, question_text, option_a, option_b, option_c, option_d, position)
SELECT topic.id, question_text, option_a, option_b, option_c, option_d, position
FROM (
  SELECT id FROM psychology_topic
  WHERE title = 'Sức khỏe tinh thần và áp lực học đường'
    AND teacher_id = (SELECT id FROM user WHERE role = 'teacher' ORDER BY id LIMIT 1)
  LIMIT 1
) AS topic
JOIN (
  SELECT 1 AS position, 'Trong tuần gần đây, bạn cảm thấy áp lực học tập ở mức nào?' AS question_text, 'Nhẹ, vẫn kiểm soát được' AS option_a, 'Có áp lực nhưng xử lý được' AS option_b, 'Khá nặng và thường xuyên' AS option_c, 'Rất nặng, khó chịu hầu hết thời gian' AS option_d
  UNION ALL SELECT 2, 'Bạn có ngủ đủ để hôm sau tỉnh táo không?', 'Thường xuyên đủ', 'Đôi lúc thiếu ngủ', 'Thiếu ngủ nhiều ngày', 'Gần như luôn mệt vì thiếu ngủ'
  UNION ALL SELECT 3, 'Khi học bài, khả năng tập trung của bạn thế nào?', 'Tập trung tốt', 'Thỉnh thoảng xao nhãng', 'Dễ mất tập trung', 'Rất khó tập trung'
  UNION ALL SELECT 4, 'Bạn có hay lo mình làm không đủ tốt không?', 'Hiếm khi', 'Thỉnh thoảng', 'Khá thường xuyên', 'Gần như luôn luôn'
  UNION ALL SELECT 5, 'Sau giờ học, cơ thể bạn thường cảm thấy ra sao?', 'Còn năng lượng', 'Hơi mệt', 'Mệt rõ rệt', 'Kiệt sức'
  UNION ALL SELECT 6, 'Bạn có thời gian nghỉ ngơi thật sự trong ngày không?', 'Có đều đặn', 'Có nhưng ít', 'Rất ít', 'Gần như không có'
  UNION ALL SELECT 7, 'Khi điểm số không như mong muốn, bạn thường nghĩ gì?', 'Xem lại để cải thiện', 'Buồn một chút rồi cố tiếp', 'Tự trách khá nhiều', 'Thấy mình kém và mất động lực'
  UNION ALL SELECT 8, 'Bạn có cảm thấy được gia đình lắng nghe không?', 'Có, khá thường xuyên', 'Có nhưng chưa nhiều', 'Ít khi', 'Hầu như không'
  UNION ALL SELECT 9, 'Bạn có cảm thấy được bạn bè hỗ trợ không?', 'Có bạn để chia sẻ', 'Có nhưng không thường xuyên', 'Ít người hiểu mình', 'Cảm thấy khá cô đơn'
  UNION ALL SELECT 10, 'Bạn có né tránh việc học vì quá căng thẳng không?', 'Hiếm khi', 'Thỉnh thoảng', 'Khá thường xuyên', 'Rất thường xuyên'
  UNION ALL SELECT 11, 'Bạn có bị đau đầu/đau bụng/mệt mỏi khi áp lực không?', 'Hiếm khi', 'Đôi khi', 'Nhiều lần trong tuần', 'Gần như thường xuyên'
  UNION ALL SELECT 12, 'Bạn có thấy hứng thú với những hoạt động mình từng thích không?', 'Vẫn hứng thú', 'Giảm nhẹ', 'Giảm khá nhiều', 'Gần như không còn'
  UNION ALL SELECT 13, 'Khi có nhiều việc cùng lúc, bạn thường xử lý thế nào?', 'Lập thứ tự ưu tiên', 'Làm từng việc một', 'Bối rối và trì hoãn', 'Cảm thấy quá tải'
  UNION ALL SELECT 14, 'Bạn có tự so sánh mình với bạn khác không?', 'Hiếm khi', 'Đôi lúc', 'Khá thường xuyên', 'Rất thường xuyên và thấy áp lực'
  UNION ALL SELECT 15, 'Mức độ tự tin của bạn trong học tập hiện tại ra sao?', 'Khá tự tin', 'Tạm ổn', 'Đang giảm', 'Rất thiếu tự tin'
  UNION ALL SELECT 16, 'Bạn có dám nhờ thầy cô/bạn bè hỗ trợ khi không hiểu bài không?', 'Dễ dàng nhờ hỗ trợ', 'Có nhưng hơi ngại', 'Ít khi hỏi', 'Hầu như không dám hỏi'
  UNION ALL SELECT 17, 'Bạn có thường nghĩ về tương lai đến mức lo lắng không?', 'Hiếm khi', 'Thỉnh thoảng', 'Khá thường xuyên', 'Rất thường xuyên'
  UNION ALL SELECT 18, 'Khi bị áp lực, bạn có hành động giúp bản thân bình tĩnh lại không?', 'Có cách rõ ràng', 'Có thử vài cách', 'Ít khi làm được', 'Không biết cách'
  UNION ALL SELECT 19, 'Bạn có muốn được tư vấn hoặc trò chuyện với người lớn đáng tin cậy không?', 'Chưa cần nhưng sẵn sàng', 'Có thể sẽ cần', 'Khá muốn', 'Rất cần được hỗ trợ'
  UNION ALL SELECT 20, 'Nếu tự chấm sức khỏe tinh thần tuần này, bạn chọn mức nào?', 'Ổn định', 'Hơi dao động', 'Đang căng thẳng', 'Cần được quan tâm nhiều hơn'
) AS questions;

COMMIT;
