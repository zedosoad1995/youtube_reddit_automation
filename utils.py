from auth import headers
import cv2
import datetime
from math import floor
import os
from PIL import Image
from pydub import AudioSegment
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


FPS = 24
BG_COLOR = (27, 26, 26)
comment_class_name = 't1_i9sf3o2'
api = 'https://oauth.reddit.com'


def cover_text_to_be_read(browser, comment_element, comment_text_element, end_sentence_idx, right_text_pos, left_text_pos, bottom_text_pos, base_img):
    mult = 1
    line_right, line_top, line_bottom = get_line_being_read_pos(browser, comment_text_element, end_sentence_idx)

    line_rect_start_point = (round(mult*(line_right - comment_element.rect['x'])), round(mult*(line_top - comment_element.rect['y'])))
    line_rect_end_point = (right_text_pos, round(mult*(line_bottom - comment_element.rect['y'])))
    
    img = base_img.copy()
    img = cv2.rectangle(img, line_rect_start_point, line_rect_end_point, BG_COLOR, -1)
    start_point = (left_text_pos, round(mult*(line_bottom - comment_element.rect['y'])))
    end_point = (right_text_pos, bottom_text_pos)
    return cv2.rectangle(img, start_point, end_point, BG_COLOR, -1)


def get_line_being_read_pos(browser, comment_text_element, end_sentence_idx):
    _, node_idx, char_idx = end_sentence_idx
    rect = browser.execute_script("var range = document.createRange(); var ele=arguments[0].children.item(arguments[2]); range.setStart(ele.childNodes[0], arguments[1]); range.setEnd(ele.childNodes[0], arguments[1]+1); return range.getClientRects();", comment_text_element, char_idx, node_idx)
    right = rect[0]['right']
    top = rect[0]['top']
    bottom = rect[0]['bottom']

    return right, top, bottom


def get_audio_from_sentence(text2speech_engine, sentence):
    text2speech_engine.save_to_file(sentence, "data/sentence.wav")
    text2speech_engine.runAndWait()
    return AudioSegment.from_wav("data/sentence.wav")


def assign_text_to_comment(comment_text_element, text, browser):
    paragraphs = text.split('\n\n')
    text = ''.join([f'<p class="_1qeIAgB0cPwnLhDF9XSiJM">{p}</p>' for p in paragraphs])
    #text = text.replace('\n\n', '<br style="line-height:22px;">')
    browser.execute_script("var ele=arguments[0]; ele.innerHTML = arguments[1];", comment_text_element, text)
    return comment_text_element.text


def get_reddit_template():
    browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    browser.get('file://' + os.path.realpath('reddit_template.html'))
    return browser


def get_text_element_from_comment(class_name, browser):
    xpath_value = f'//div[@id="{class_name}"]/div[starts-with(@class,\'Comment\')]/div[2]/div[@data-testid="comment"]/div'
    return browser.find_element(by=By.XPATH, value=xpath_value)


def merge_imgs_vertical(file_list):
    imgs, heights, widths = [], [], []
    for file in file_list:
        img = Image.open(file)
        (w, h) = img.size

        heights.append(h)
        widths.append(w)
        imgs.append(img)

    merged_width = max(widths)
    merged_height = sum(heights)

    merged_img = Image.new('RGB', (merged_width, merged_height))

    cum_height = 0
    for i, img in enumerate(imgs):
        merged_img.paste(im=img, box=(0, cum_height))
        cum_height += heights[i]
    
    return merged_img


def find_occurrences(text, char_to_find):
    idx_node = 0
    idx_ch_in_node = 0
    list_occurrences: list[tuple[int, int, int]] = []
    for i, ch in enumerate(text[:-1]):
        if ch == '\n':
            idx_ch_in_node = 0
            idx_node += 1
            continue

        if ch == char_to_find:
            list_occurrences.append((i, idx_node, idx_ch_in_node))
        
        idx_ch_in_node += 1

    # Always contain last occurrence
    list_occurrences.append((len(text) - 1, idx_node, idx_ch_in_node))

    return list_occurrences


def make_video_segment_from_sentence(img, duration, vid_writter, fps=24):

    img_with_border = cv2.copyMakeBorder(img, top=0, bottom=698-img.shape[0], left=0, right=0, borderType=cv2.BORDER_CONSTANT, value=(0, 0, 0))

    for _ in range(floor(duration*fps)):
        vid_writter.write(img_with_border)


def make_clip_from_comment(browser, text, vid_writter, text2speech, full_speech=None):
    comment_text_element = get_text_element_from_comment(comment_class_name, browser)

    text = assign_text_to_comment(comment_text_element, text, browser)

    comment_element = browser.find_element(by=By.CSS_SELECTOR, value=f'div#{comment_class_name}')
    comment_element.screenshot('data/comment.png')
    base_img = cv2.imread('data/comment.png')

    end_sentence_idxs = find_occurrences(text, '.')

    # Position of the text, relative to the comment
    left_text_pos = comment_text_element.location['x'] - comment_element.location['x']
    bottom_text_pos = comment_text_element.location['y'] + comment_text_element.rect['height'] - comment_element.location['y']
    right_text_pos = comment_text_element.location['x'] + comment_text_element.rect['width'] - comment_element.location['x']

    prev_idx = 0
    for end_sentence_idx in end_sentence_idxs:
        sentence = text[prev_idx:end_sentence_idx[0]+1]
        new_speech = get_audio_from_sentence(text2speech, sentence)

        full_speech = full_speech.append(new_speech, 0) if full_speech is not None else new_speech

        img = cover_text_to_be_read(
            browser, 
            comment_element, 
            comment_text_element, 
            end_sentence_idx, 
            right_text_pos, 
            left_text_pos, 
            bottom_text_pos, 
            base_img)

        make_video_segment_from_sentence(img, new_speech.duration_seconds, vid_writter, fps=FPS)

        prev_idx = end_sentence_idx[0] + 1

    return full_speech


def get_best_submission(req, from_date=None, to_date=None):    
    res = requests.get(req, headers=headers)
    res = res.json()

    while True:
        submissions = res['data']['children']
        if len(submissions) == 0:
            break

        for submission in submissions:
            if submission['data']['created_utc'] >= to_date or submission['data']['created_utc'] < from_date:
                continue
        
            return submission['data']

        after = submissions[-1]['data']['name']
        new_req = req + f'&after={after}'
        res = requests.get(new_req, headers=headers)
        res = res.json()

    return None


def get_best_post_yesterday(subreddit):
    dt = datetime.datetime.now(datetime.timezone.utc)
    utc_time = dt.replace(tzinfo=datetime.timezone.utc)
    now = utc_time.timestamp()
    one_day_ago = int(now - 86400)
    two_days_ago = int(one_day_ago - 86400)
    three_days_ago = int(two_days_ago - 86400)

    return get_best_submission(f'{api}/r/{subreddit}/top.json?limit=100&t=week', two_days_ago, one_day_ago)


def get_top_comments_from_submission(url, n_comments=10):
    last_idx = url[:-1].rfind('/')
    url = url[:last_idx] + '.json?limit=100&sort=top'
    url = url.replace('https://www.reddit.com', api)

    res = requests.get(url, headers=headers)
    res = res.json()

    comments = []
    for comment in res[1]['data']['children'][:n_comments]:
        comments.append(comment['data']['body'])

    return comments
