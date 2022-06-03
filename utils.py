from auth import headers
import cv2
import datetime
import glob
from math import floor
from moviepy.editor import AudioFileClip
import os
from PIL import Image
from pydub import AudioSegment
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from params import BG_COLOR, FPS, HORIZONTAL_MARGIN, IS_COMMENT_ORIGINAL_SIZE, OPEN_CV_VIDEO_WRITTER, VIDEO_HEIGHT, COMMENT_CLASS_NAME, VIDEO_WIDTH, API


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


def get_bg_music(video, audio_filepath):
    original_audio = AudioSegment.from_wav(audio_filepath)
    looped_audio = original_audio
    crossfade_duration = 100

    n_reps = floor((video.duration + crossfade_duration)/original_audio.duration_seconds)
    for i in range(n_reps):
        if i == n_reps - 1:
            # To avoid repeating audio, when it will be played for a very short time. Better to end the video with a few seconds of silence
            if (video.duration + crossfade_duration) % original_audio.duration_seconds < 20000:
                break

        looped_audio = looped_audio.append(original_audio, crossfade=crossfade_duration)

    fade_out_duration = 15000
    looped_audio = looped_audio[:video.end*1000]
    looped_audio = looped_audio.fade_out(fade_out_duration)
    looped_audio = looped_audio - 15
    looped_audio.export("data/bg_music.wav", format="wav")
    return AudioFileClip('data/bg_music.wav')



def get_audio_from_sentence(text2speech_engine, sentence):
    text2speech_engine.save_to_file(sentence, "data/sentence.wav")
    text2speech_engine.runAndWait()
    return AudioSegment.from_wav("data/sentence.wav")


def set_text_comment(class_name, text, browser):
    regex_link = r'\[(.+?)\]\((?:.+?)\)'
    text = re.sub(
        pattern=regex_link, 
        repl='\\1', 
        string=text
    )
    regex_url = r'[(?:http(s)?):\/\/(www\.)?a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b(?:[-a-zA-Z0-9@:%_\+.~#?&\/=]*)'
    regex_link = regex_url + r'\[(.+?)\]'
    text = re.sub(
        pattern=regex_link, 
        repl='\\1', 
        string=text
    )
    text = re.sub(
        pattern=regex_url, 
        repl='', 
        string=text
    )
    text = re.sub(
        pattern=r"(?:&gt;!|!&lt;)", 
        repl='', 
        string=text
    )
    text = re.sub(
        pattern=r"__(.+?)__", 
        repl='\\1', 
        string=text
    )
    text = re.sub(
        pattern=r"[“”]", 
        repl='"', 
        string=text
    )

    regex_exp_new_lines = r"(?:\s*\n{2,}\s*)+"
    paragraphs = re.split(regex_exp_new_lines, text)
    for i, par in enumerate(paragraphs):
        paragraphs[i] = re.sub(r'\s{2,}', ' ', par)
    text = ''.join([f'<p class="_1qeIAgB0cPwnLhDF9XSiJM">{p}</p>' for p in paragraphs])
    xpath_value = f'//div[@id="{class_name}"]/div[starts-with(@class,\'Comment\')]/div[2]/div[@data-testid="comment"]/div'
    comment_text_element =  browser.find_element(by=By.XPATH, value=xpath_value)
    browser.execute_script("var ele=arguments[0]; ele.innerHTML = arguments[1];", comment_text_element, text)
    return comment_text_element


def get_reddit_template():
    browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    browser.maximize_window()
    browser.get('file://' + os.path.realpath('reddit_template.html'))
    return browser


def set_title(browser, question):
    css_value = 'div._29WrubtjAcKqzJSPdQqQ4h>h1'
    question_text_element = browser.find_element(by=By.CSS_SELECTOR, value=css_value)
    browser.execute_script("var ele=arguments[0]; ele.innerHTML = arguments[1];", question_text_element, question)


def get_title_element(browser):
    css_value = 'div._1oQyIsiPHYt6nx7VOmd1sz._2rszc84L136gWQrkwH6IaM.Post.t3_uwhdj4'
    return browser.find_element(by=By.CSS_SELECTOR, value=css_value)


def set_num_likes_title(browser, num_likes):
    if num_likes/10000 >= 1:
        num_likes = str(round(num_likes/1000, 1)) + 'k'
    css_value = 'div._1rZYMD_4xY3gRcSS3p8ODO._3a2ZHWaih05DgAOtvu6cIo._2iiIcja5xIjg-5sI4ECvcV>div'
    title_upvotes_element = browser.find_element(by=By.CSS_SELECTOR, value=css_value)
    browser.execute_script("var ele=arguments[0]; ele.innerHTML = arguments[1];", title_upvotes_element, num_likes)


def set_num_comments(browser, num_comments):
    if num_comments/10000 >= 1:
        num_comments = str(round(num_comments/1000, 1)) + 'k'
    css_value = 'div._1UoeAeSRhOKSNdY_h3iS1O._3m17ICJgx45k_z-t82iVuO._3U_7i38RDPV5eBv7m4M-9J._2qww3J5KKzsD7e5DO0BvvU>span>div'
    title_comments_element = browser.find_element(by=By.CSS_SELECTOR, value=css_value)
    browser.execute_script("var ele=arguments[0]; ele.innerHTML = arguments[1];", title_comments_element, num_comments)


def set_user_title(browser, username):
    username = f'u/{username}'
    css_value = 'div#UserInfoTooltip--t3_uwhdj4--lightbox>a'
    title_user_element = browser.find_element(by=By.CSS_SELECTOR, value=css_value)
    browser.execute_script("var ele=arguments[0]; ele.innerHTML = arguments[1];", title_user_element, username)


def set_post_time(browser, time):
    css_value = 'div.cZPZhMe-UCZ8htPodMyJ5:nth-of-type(2n)>div>a'
    title_time_element = browser.find_element(by=By.CSS_SELECTOR, value=css_value)
    browser.execute_script("var ele=arguments[0]; ele.innerHTML = arguments[1];", title_time_element, time)


def set_post_subreddit(browser, subreddit):
    img_element_sel = '#t3_uwhdj4 > div > div._14-YvdFiW5iVvfe5wdgmET > div._2dr_3pZUCk8KfJ-x0txT_l > a > img'
    sub_name_element_sel = '#t3_uwhdj4 > div > div._14-YvdFiW5iVvfe5wdgmET > div.cZPZhMe-UCZ8htPodMyJ5 > div._3AStxql1mQsrZuUIFP9xSg.nU4Je7n-eSXStTBAPMYt8 > div:nth-child(1) > a'

    img_icon_url = get_subreddit_img_url(subreddit)

    img_el = browser.find_element(by=By.CSS_SELECTOR, value=img_element_sel)
    browser.execute_script('var ele=arguments[0]; ele.setAttribute("src", arguments[1]);', img_el, img_icon_url)

    sub_name_el = browser.find_element(by=By.CSS_SELECTOR, value=sub_name_element_sel)
    browser.execute_script("var ele=arguments[0]; ele.innerHTML = arguments[1];", sub_name_el, f'r/{subreddit}')


def get_subreddit_img_url(subreddit):
    url = f'{API}/r/{subreddit}/about.json'
    res = requests.get(url, headers=headers)
    res = res.json()

    return res['data']['community_icon'].replace('amp;', '')


def set_user_comment(browser, username):
    css_value = 'a.wM6scouPXXsFDSZmZPHRo[href="/user/Augie777/"]'
    comment_user_element = browser.find_element(by=By.CSS_SELECTOR, value=css_value)
    browser.execute_script("var ele=arguments[0]; ele.innerHTML = arguments[1];", comment_user_element, username)


def set_score_comment(browser, score):
    if score/1000 >= 1:
        score = str(round(score/1000, 1)) + 'k'
    css_value = 'div#vote-arrows-t1_i9sf3o2>div'
    score_user_element = browser.find_element(by=By.CSS_SELECTOR, value=css_value)
    browser.execute_script("var ele=arguments[0]; ele.innerHTML = arguments[1];", score_user_element, score)


def set_comment_time(browser, time):
    css_value = 'a#CommentTopMeta--Created--t1_i9sf3o2inOverlay'
    title_time_element = browser.find_element(by=By.CSS_SELECTOR, value=css_value)
    browser.execute_script("var ele=arguments[0]; ele.innerHTML = arguments[1];", title_time_element, time)


def set_user_img(browser, username):
    url = f'{API}/user/{username}/about.json'
    res = requests.get(url, headers=headers)
    res = res.json()

    # TODO: Change to random profiles
    if 'icon_img' not in res['data']:
        return
    img_url = res['data']['icon_img']
    img_url = img_url.split('?')[0]

    css_value = 'a[href="/user/Augie777/"] img'
    profile_img_element = browser.find_element(by=By.CSS_SELECTOR, value=css_value)
    browser.execute_script('var ele=arguments[0]; ele.setAttribute("src", arguments[1]);', profile_img_element, img_url)



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


def find_end_sentence(text):


    idx_node = 0
    idx_ch_in_node = 0
    list_occurrences: list[tuple[int, int, int]] = []
    for i, ch in enumerate(text[:-1]):
        if ch == '\n':
            new_line_occurence = (i-1, idx_node, idx_ch_in_node-1)
            # To avoid repetition
            if len(list_occurrences) == 0 or new_line_occurence != list_occurrences[-1]:
                list_occurrences.append((i-1, idx_node, idx_ch_in_node-1))
            idx_ch_in_node = 0
            idx_node += 1
            continue

        if re.search(r'[.!?:]+["|\']?[^.!?:"\']$', text[:i+2]):
            list_occurrences.append((i, idx_node, idx_ch_in_node))
        
        idx_ch_in_node += 1

    # Always contain last occurrence
    list_occurrences.append((len(text) - 1, idx_node, idx_ch_in_node))

    return list_occurrences


def add_border_to_img(img):
    if not IS_COMMENT_ORIGINAL_SIZE:
        scaled_width = VIDEO_WIDTH - HORIZONTAL_MARGIN*2
        scaled_height = int(scaled_width/img.shape[1]*img.shape[0])
        img = cv2.resize(img, (scaled_width, scaled_height))
    elif img.shape[1] > VIDEO_WIDTH:
        scaled_height = int(VIDEO_WIDTH/img.shape[1]*img.shape[0])
        img = cv2.resize(img, (VIDEO_WIDTH, scaled_height))
    
    horizontal_border_size = (VIDEO_WIDTH - img.shape[1])//2
    horizontal_offset = (VIDEO_WIDTH - img.shape[1])%2

    vertical_border_size = (VIDEO_HEIGHT - img.shape[0])//2
    vertical_offset = (VIDEO_HEIGHT - img.shape[0])%2

    return cv2.copyMakeBorder(
        img, 
        top=vertical_border_size, 
        bottom=vertical_border_size+vertical_offset, 
        left=horizontal_border_size, 
        right=horizontal_border_size+horizontal_offset, 
        borderType=cv2.BORDER_CONSTANT, 
        value=BG_COLOR)

def make_video_segment_from_sentence(img, duration, vid_writter, fps=24, img_num='0000'):
    img_with_border = add_border_to_img(img)   

    if OPEN_CV_VIDEO_WRITTER:
        for _ in range(floor(duration*fps)):
            vid_writter.write(img_with_border)
    else:
        cv2.imwrite(f'imgs/{img_num}.png', img_with_border)


def make_clip_from_comment(browser, comment_text_element, vid_writter, text2speech, full_speech=None, clip_num=0, durations=[]):
    text = comment_text_element.text
    
    comment_element = browser.find_element(by=By.CSS_SELECTOR, value=f'div#{COMMENT_CLASS_NAME}')
    comment_element.screenshot('data/comment.png')
    comment_img = cv2.imread('data/comment.png')

    end_sentence_idxs = find_end_sentence(text)

    # Position of the text, relative to the comment
    left_text_pos = comment_text_element.location['x'] - comment_element.location['x']
    bottom_text_pos = comment_text_element.location['y'] + comment_text_element.rect['height'] - comment_element.location['y']
    right_text_pos = comment_text_element.location['x'] + comment_text_element.rect['width'] - comment_element.location['x']

    prev_idx = 0
    cnt = 0
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
            comment_img)

        img_num = str(clip_num).rjust(2, '0') + str(cnt).rjust(2, '0')
        make_video_segment_from_sentence(img, new_speech.duration_seconds, vid_writter, fps=FPS, img_num=img_num)
        durations.append(new_speech.duration_seconds)

        prev_idx = end_sentence_idx[0] + 1
        cnt += 1

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

    return get_best_submission(f'{API}/r/{subreddit}/top.json?limit=100&t=week', two_days_ago, one_day_ago)


def get_top_comments_from_submission(url, n_comments=10):
    last_idx = url[:-1].rfind('/')
    url = url[:last_idx] + '.json?limit=100&sort=top'
    url = url.replace('https://www.reddit.com', API)

    res = requests.get(url, headers=headers)
    res = res.json()

    comments = []
    for comment in res[1]['data']['children'][:n_comments]:
        comments.append(comment['data'])

    return comments



def create_folders(folders: str | list):
    if isinstance(folders, str):
        folders = [folders]

    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)


def remove_folders_content(folders: str | list):
    if isinstance(folders, str):
        folders = [folders]

    for folder in folders:
        files = glob.glob(folder + '/*')
        for f in files:
            os.remove(f)