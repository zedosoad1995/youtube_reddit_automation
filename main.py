import cv2
from moviepy.editor import VideoFileClip, AudioFileClip
import pyttsx3
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from utils import get_best_post_yesterday, get_reddit_template, get_top_comments_from_submission, make_clip_from_comment

text2speech = pyttsx3.init()

FPS = 24

browser = get_reddit_template()

middle_comment = browser.find_element(by=By.CSS_SELECTOR, value='div#t1_i9sxsju')

# t1_i9sf3o2 t1_i9sul17 t1_i9sxsju t1_i9t4aja t1_i9t68km
actions = ActionChains(browser)
actions.move_to_element(middle_comment).perform()

vid_writter = cv2.VideoWriter("data/output.mp4", cv2.VideoWriter_fourcc(*'mp4v'), FPS, (698, 698))

submission = get_best_post_yesterday('AskReddit')
print(submission['title'])
comments = get_top_comments_from_submission(submission['url'])

full_speech = None
for comment in comments:
    full_speech = make_clip_from_comment(browser, comment, vid_writter, text2speech, full_speech)

full_speech.export("data/combined.wav", format="wav")
vid_writter.release()
vid = VideoFileClip('data/output.mp4')
audio = AudioFileClip('data/combined.wav')
final_clip = vid.set_audio(audio)
final_clip.write_videofile("data/final.mp4")