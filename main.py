import re
import cv2
from moviepy.editor import VideoFileClip, AudioFileClip, ImageSequenceClip, CompositeAudioClip
from params import (
    COMMENT_CLASS_NAME,
    DATA_DIR, 
    FINAL_VIDEO_FILE_PATH, 
    FPS, 
    IMGS_DIR, 
    OPEN_CV_VIDEO_WRITTER,
    SUBREDDIT, 
    VIDEO_HEIGHT, 
    VIDEO_WIDTH, 
    VIDEO_WRITTER_FILE_PATH
)
import pyttsx3
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from thumbnail_utils import create_thumbnails, get_keywords
from utils import (
    add_border_to_img,
    create_folders,
    get_audio_from_sentence, 
    get_best_post_yesterday,
    get_bg_music, 
    get_reddit_template,
    get_title_element, 
    get_top_comments_from_submission, 
    make_clip_from_comment, 
    remove_folders_content,
    set_comment_time,
    set_num_comments,
    set_num_likes_title,
    set_post_subreddit,
    set_post_time,
    set_score_comment,
    set_text_comment, 
    set_title,
    set_user_comment,
    set_user_img,
    set_user_title
)

text2speech = pyttsx3.init()
text2speech.setProperty("rate", 160)

create_folders([DATA_DIR, IMGS_DIR])
remove_folders_content([DATA_DIR, IMGS_DIR])

browser = get_reddit_template()


if OPEN_CV_VIDEO_WRITTER:
    # Melhor: 'D', 'I', 'V', 'X'
    vid_writter = cv2.VideoWriter(VIDEO_WRITTER_FILE_PATH, cv2.VideoWriter_fourcc('D', 'I', 'V', 'X'), FPS, (VIDEO_WIDTH, VIDEO_HEIGHT))
else:
    vid_writter = None

submission = get_best_post_yesterday(SUBREDDIT)
set_title(browser, submission['title'])
set_num_likes_title(browser, submission['ups'])
set_num_comments(browser, submission['num_comments'])
set_user_title(browser, submission['author'])
set_post_time(browser, '1 day ago')
set_post_subreddit(browser, SUBREDDIT)
# TODO: set rewards, set time ago

#comment_post_process = re.sub(r'[^a-zA-Z\s]', '', comment['body'])
keywords = get_keywords(submission['title']) #+ ' ' + comment_post_process)
create_thumbnails(submission['title'], keywords, submission['subreddit'])

title_element = get_title_element(browser)
actions = ActionChains(browser)
actions.move_to_element(title_element).perform()
title_element.screenshot(f'{DATA_DIR}/title.png')
img = cv2.imread(f'{DATA_DIR}/title.png')
img_with_border = add_border_to_img(img)
cv2.imwrite(f'{IMGS_DIR}/0000.png', img_with_border)

durations = []
full_speech = get_audio_from_sentence(text2speech, f"r/{submission['subreddit']}: {submission['title']}")
durations.append(full_speech.duration_seconds)

comments = get_top_comments_from_submission(submission['url'], n_comments=30)

# t1_i9sf3o2 t1_i9sul17 t1_i9sxsju t1_i9t4aja t1_i9t68km

cnt = 1
for comment in comments:
    if 'stickied' in comment and comment['stickied']:
        continue
    author = comment['author'] if 'author' in comment else 'deleted'
    if author == 'deleted':
        continue
    set_user_comment(browser, author)
    set_score_comment(browser, comment['ups'])
    set_comment_time(browser, '1 day ago')
    set_user_img(browser, comment['author'])
    #comment['body'] = '"Something." asdasd \'kids?\'.a'
    comment_text_element = set_text_comment(COMMENT_CLASS_NAME, comment['body'], browser)
    
    # Skips comments to large to screenshot in one go
    approx_num_lines = comment_text_element.rect['height']//int(comment_text_element.value_of_css_property('lineHeight')[:-2])
    if approx_num_lines >= 15:
        continue

    middle_comment = browser.find_element(by=By.CSS_SELECTOR, value='div#t1_i9sul17')
    print('start', comment['body'], comment_text_element.text)
    actions = ActionChains(browser)
    actions.move_to_element(middle_comment).perform()
    full_speech = make_clip_from_comment(browser, comment_text_element, vid_writter, text2speech, full_speech=full_speech, clip_num=cnt, durations=durations)
    cnt += 1

full_speech.export("data/combined.wav", format="wav")
audio = AudioFileClip('data/combined.wav')

if OPEN_CV_VIDEO_WRITTER:
    vid_writter.release()
    vid = VideoFileClip(VIDEO_WRITTER_FILE_PATH)
    final_clip = vid.set_audio(audio)
    final_clip.write_videofile(FINAL_VIDEO_FILE_PATH, preset='placebo', codec='rawvideo')
else:
    vid = ImageSequenceClip(IMGS_DIR, durations=durations)
    vid = vid.set_fps(FPS)
    bg_music = get_bg_music(vid, 'saved_data/bgmusic2.wav')
    audio = CompositeAudioClip([audio, bg_music])
    vid = vid.set_audio(audio)
    vid.write_videofile(FINAL_VIDEO_FILE_PATH)
