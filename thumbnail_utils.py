import cv2
from math import floor
import nltk
import numpy as np
import os
from PIL import ImageFont, ImageDraw, Image
from rake_nltk import Rake
import requests
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from urllib.request import urlopen
from webdriver_manager.chrome import ChromeDriverManager

from params import DATA_DIR
from utils import get_subreddit_img_url

VIDEO_WIDTH = 852
VIDEO_HEIGHT = 420
LEFT_MARGIN = 40
TOP_MARGIN = 10
LOGO_HEIGHT_PERC = 0.15

def write_text_in_image(img, text, max_text_width, logo_bottom, keywords):
    keywords = [w.lower() for sentence in keywords for w in sentence.split()]
    max_text_width = min(max_text_width, VIDEO_WIDTH)

    fake_img = Image.new("L", (200, 200), color=0)  
    draw = ImageDraw.Draw(fake_img)
    
    vertical_space_perc_of_font_height = 0.1
    words = text.split()
    for font_size in range(8, 100):
        font = ImageFont.truetype("saved_data/impact.ttf", font_size)
        _, height = draw.textsize('Test', font=font)  
        y_start = logo_bottom + height*vertical_space_perc_of_font_height

        idx_ini = 0
        idx_fin = 1
        does_not_fit = False
        y = 0
        string_info = []
        while True:
            words_in_line = ' '.join(words[idx_ini:idx_fin])
            width, height = draw.textsize(words_in_line, font=font) 

            if y + height*(1 + vertical_space_perc_of_font_height) + y_start > VIDEO_HEIGHT:
                does_not_fit = True
                break

            if idx_ini >= len(words) or idx_fin > len(words):
                if (len(string_info) > 0 and string_info[-1]['y'] != y) or len(string_info) == 0:
                    string_info.append({"y": y + height + y_start, "idx_ini": idx_ini, "idx_fin": len(words)})
                if len(string_info) > 0 and string_info[-1]['idx_fin'] != len(words):
                    does_not_fit = True
                break

            if width + LEFT_MARGIN > max_text_width:
                idx_fin -= 1
                string_info.append({"y": y + height + y_start, "idx_ini": idx_ini, "idx_fin": idx_fin})
                y += height*(1 + vertical_space_perc_of_font_height)

                idx_ini = idx_fin
                idx_fin = idx_ini + 1
            else:
                idx_fin += 1
            
        if does_not_fit:
            break
        
        best_height = height
        best_font = font
        best_string_info = string_info

    n_lines = len(best_string_info)
    empty_space_y = VIDEO_HEIGHT - logo_bottom - best_height*n_lines
    desired_empty_space_y = empty_space_y/(n_lines + 2)

    prev_y = logo_bottom
    for str_info in best_string_info:
        str_info['y'] = prev_y + desired_empty_space_y
        prev_y += best_height + desired_empty_space_y


    fill = ' o '
    w_fill, _ = draw.textsize(' o ', font=font)
    test_img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), (0,0,0)) # scrap image
    draw_test = ImageDraw.Draw(test_img)

    cv2.imwrite('data/temp.png', img)
    img = Image.open('data/temp.png') 
    draw = ImageDraw.Draw(img)
    for info in best_string_info:
        line_text = ' '.join(text.split()[info['idx_ini']:info['idx_fin']])
        line_text_lower = line_text.lower()
        kw_positions = sorted([(line_text_lower.find(w), line_text_lower.find(w) + len(w)) for w in keywords if w in line_text_lower], key=lambda x: x[0])

        x = int(LEFT_MARGIN)
        y = int(info['y'])

        for i, ch in enumerate(line_text):
            w_full, _ = draw_test.textsize(fill+ch, font=font)
            w = w_full - w_fill

            belongs_to_keyword = any([True for ini, fin in kw_positions if i >= ini and i < fin])
            color = (249, 241, 21) if belongs_to_keyword else (255, 255, 255)

            draw.text((x, y), ch, font=best_font, fill=color)

            x += w

    img.save('data/temp.png')
    return cv2.imread('data/temp.png')


def add_image_to_thumbnail(background, foreground):
    h, w, _ = foreground.shape
    scaled_width = int(VIDEO_HEIGHT/h*w)
    foreground = cv2.resize(foreground, (scaled_width, VIDEO_HEIGHT))

    foreground_width = min(scaled_width, int(VIDEO_WIDTH/2))
    max_text_width = VIDEO_WIDTH - foreground_width
    dissipation_border_size = int(0.25*foreground_width)
    max_text_width += int(dissipation_border_size/2)

    crop_foreground = foreground[:, (foreground.shape[1]-foreground_width)//2:(foreground.shape[1]+foreground_width)//2]

    mask = np.zeros((VIDEO_HEIGHT, VIDEO_WIDTH))
    mask[:, -foreground_width:] = 1

    def gaussian(x, mu, sig):
        return np.exp(-np.power(x - mu, 2.) / (2 * np.power(sig, 2.)))

    x = np.array(list(range(dissipation_border_size)))
    y = gaussian(x, dissipation_border_size-1, dissipation_border_size/3)

    mask[:, -foreground_width:(-foreground_width+dissipation_border_size)] = np.repeat(y[None, :], VIDEO_HEIGHT, axis=0)

    background[:, -foreground_width:] = crop_foreground
    img = background * mask[..., None]
    return img.astype(np.uint8), max_text_width


def get_images_from_text(phrase, n_imgs=10):
    phrase = re.sub(r'\s+', '%20', phrase)
    headers = {
        'accept': '*/*',
        'accept-encoding': 'gzip, deflate, br',
        'accept-language': 'pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7,ja;q=0.6',
        'cookie': 'ugid=a8576f86a6929608007c3e587480ee255477880; xp-search-explore-top-affiliate-outside-feed-x-v2=a; _ga=GA1.2.482463119.1654553829; uuid=67f15230-e5e6-11ec-931b-b13fcfaa8bcb; xpos=%7B%7D; azk=67f15230-e5e6-11ec-931b-b13fcfaa8bcb; azk-ss=true; lux_uid=165478656407175945; _sp_ses.0295=*; _gid=GA1.2.930424424.1654786565; _gat=1; _sp_id.0295=1ddb14c2-acbe-475c-8191-17b602b957cc.1654553829.3.1654787298.1654619239.957f939f-5722-47d9-bb1e-4cf179d47754',
        'referer': 'https://unsplash.com/s/photos/sex',
        'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="102", "Google Chrome";v="102"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.63 Safari/537.36',
        'x-affiliates-request-id': 'SearchPhotos',
        'x-locale': 'en-US'
    }
    #url = f'https://unsplash.com/ngetty/v3/search/images/creative?fields=display_set%2Creferral_destinations%2Ctitle&page_size=28&phrase={phrase}&sort_order=best_match&graphical_styles=photography&exclude_nudity=true&exclude_editorial_use_only=true'
    url = f'https://unsplash.com/napi/search?query={phrase}&per_page=10&exclude_editorial_use_only=true'
    res = requests.get(url, headers=headers)
    res = res.json()

    final_imgs = []
    for img in res['photos']['results']:
        final_imgs.append(img['urls']['regular'])
        if len(final_imgs) >= n_imgs:
            break

    return final_imgs


def create_subreddit_logo(filepath, subreddit):
    main_element_sel = '#AppRouter-main-content > div > div > div._3ozFtOe6WpJEMUtxDOIvtU'
    text_element_sel = '#AppRouter-main-content > div > div > div._3ozFtOe6WpJEMUtxDOIvtU > div.MSTY2ZpsdupobywLEfx9u > div > div.QscnL9OySMkHhGudEvEya > div > div._3TG57N4WQtubLLo8SbAXVF > h1'
    img_element_sel = '#AppRouter-main-content > div > div > div._3ozFtOe6WpJEMUtxDOIvtU > div.MSTY2ZpsdupobywLEfx9u > div > div.QscnL9OySMkHhGudEvEya > img'

    browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    browser.maximize_window()
    browser.get('file://' + os.path.realpath('subreddit_logo_template.html'))

    text_el = browser.find_element(by=By.CSS_SELECTOR, value=text_element_sel)
    browser.execute_script("var ele=arguments[0]; ele.innerHTML = arguments[1];", text_el, f'r/{subreddit}')

    img_icon_url = get_subreddit_img_url(subreddit)

    img_el = browser.find_element(by=By.CSS_SELECTOR, value=img_element_sel)
    browser.execute_script('var ele=arguments[0]; ele.setAttribute("src", arguments[1]);', img_el, img_icon_url)

    main_el = browser.find_element(by=By.CSS_SELECTOR, value=main_element_sel)
    main_el.screenshot(filepath)

    img = cv2.imread(filepath)
    img = img[:, img_el.location['x']:(text_el.location['x'] + int(text_el.rect['width']))]
    cv2.imwrite(filepath, img)

    img_list = np.reshape(img, (-1, 3))
    img_list = np.sort(img_list, axis=0)
    img_list = np.unique(img_list, axis=0)

    expected_color = 0
    non_existing_color = [0, 0, 0]
    for color in img_list:
        color_int = (256**2)*color[0] + 256*color[1] + color[2]
        if color_int != expected_color:
            non_existing_color[0] = int(expected_color/(256**2))
            expected_color -= non_existing_color[0]
            non_existing_color[1] = int(expected_color/256)
            expected_color -= non_existing_color[1]
            non_existing_color[2] = expected_color

            break

        expected_color = color_int + 1

    new_bg_color_str = f'rgb({non_existing_color[2]}, {non_existing_color[1]}, {non_existing_color[0]})'

    upper_bg_element_sel = '#AppRouter-main-content > div > div > div._3ozFtOe6WpJEMUtxDOIvtU > span'
    lower_bg_element_sel = '#AppRouter-main-content > div > div > div._3ozFtOe6WpJEMUtxDOIvtU > div.MSTY2ZpsdupobywLEfx9u'

    upper_bg_el = browser.find_element(by=By.CSS_SELECTOR, value=upper_bg_element_sel)
    lower_bg_el = browser.find_element(by=By.CSS_SELECTOR, value=lower_bg_element_sel)

    browser.execute_script('var ele=arguments[0]; ele.style.backgroundColor = arguments[1];', upper_bg_el, new_bg_color_str)
    browser.execute_script('var ele=arguments[0]; ele.style.backgroundColor = arguments[1];', lower_bg_el, new_bg_color_str)

    main_el.screenshot(filepath)
    img = cv2.imread(filepath)
    img = img[:, img_el.location['x']:(text_el.location['x'] + int(text_el.rect['width']))]
    cv2.imwrite(filepath, img)

    img = Image.open(filepath)
    rgba = img.convert('RGBA')
    datas = rgba.getdata()

    new_data = []
    for item in datas:
        if item[0] == non_existing_color[2] and item[1] == non_existing_color[1] and item[2] == non_existing_color[0]:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)

    rgba.putdata(new_data)
    rgba.save(filepath, 'PNG')


def add_logo_to_thumbnail(bg, subreddit_logo):
    mask = (subreddit_logo[..., 3]/255).astype(np.int8)
    mask_inv = 1 - mask

    roi = bg[TOP_MARGIN:(subreddit_logo.shape[0]+TOP_MARGIN), LEFT_MARGIN:(subreddit_logo.shape[1]+LEFT_MARGIN)]
    bg_roi = cv2.bitwise_and(roi, roi, mask = mask_inv)
    logo_no_bg = cv2.bitwise_and(subreddit_logo, subreddit_logo, mask = mask)

    bg[TOP_MARGIN:(subreddit_logo.shape[0]+TOP_MARGIN), LEFT_MARGIN:(subreddit_logo.shape[1]+LEFT_MARGIN)] = cv2.add(logo_no_bg[..., :3], bg_roi)
    return bg, subreddit_logo.shape[0] + TOP_MARGIN


def get_keywords(text):
    nltk.download('stopwords')
    nltk.download('punkt')
    r = Rake()
    r.extract_keywords_from_text(text)

    return r.get_ranked_phrases()



def create_thumbnails(title, keywords, subreddit):
    subreddit_logo_filepath = f'{DATA_DIR}/subreddit_logo.png'
    create_subreddit_logo(subreddit_logo_filepath, subreddit)

    black_bg = np.zeros((VIDEO_HEIGHT,VIDEO_WIDTH,3), dtype=np.uint8)
    subreddit_logo = cv2.imread(subreddit_logo_filepath, cv2.IMREAD_UNCHANGED)
    logo_desired_height = floor(LOGO_HEIGHT_PERC*VIDEO_HEIGHT)
    logo_desired_width = floor(logo_desired_height/subreddit_logo.shape[0]*subreddit_logo.shape[1])
    subreddit_logo = cv2.resize(subreddit_logo, (logo_desired_width, logo_desired_height), interpolation=cv2.INTER_AREA)

    for image_search_text in keywords:
        img_urls = get_images_from_text(image_search_text)

        for i, img_url in enumerate(img_urls):
            req = urlopen(img_url)
            arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
            foreground = cv2.imdecode(arr, -1)
            img, max_text_width = add_image_to_thumbnail(black_bg, foreground)
            img, logo_bottom = add_logo_to_thumbnail(img, subreddit_logo)

            img = write_text_in_image(img, title, max_text_width, logo_bottom, keywords)
            cv2.imwrite(f"{DATA_DIR}/thumbnail_{image_search_text.replace(' ', '')}_{i}.png", img)
