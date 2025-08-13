'''个人定制模式，自动处理看完的影片，跟刮削无关'''
'''填写javdb.cookies后，自动将放在特定位置的影片在javdb上标记看过并评分并删除或移动'''
'''文件夹监视由外部处理，本工具不做常驻进程'''

import os
import time
import shutil
import requests
import logger
import config
from lxml import etree
from core.scrapinglib.custom.javdb import Javdb
from utils.number_parser import get_number

def run():
    
    dir_keep = config.getStrValue("autoRate.dir_keep")
    dir_keep_to = config.getStrValue("autoRate.dir_keep_to")
    dir_delete_4 = config.getStrValue("autoRate.dir_delete_4")
    dir_delete_5 = config.getStrValue("autoRate.dir_delete_5")
    movies_dir_keep = []
    movies_dir_delete_4 = []
    movies_dir_delete_5 = []
    db = Javdb()
    
    if os.path.exists(dir_keep):
        movies_dir_keep = os.listdir(dir_keep)
        list_id = config.getStrValue("autoRate.db_list_id")
        for movie in movies_dir_keep:
            full_path = os.path.join(dir_keep,movie)
            logger.info(f"auto rate movie: {full_path}")
            number = get_number(movie)
            if number is None:
                continue
            auto_rate(db,number,"5")
            shutil.move(full_path, os.path.join(dir_keep_to,movie))
            try:
                add_list(db,number,list_id)
            except Exception as e:
                logger.error(f"add_list error. number:[{number}] info: {e}" )
            

    if os.path.exists(dir_delete_4):
        movies_dir_delete_4 = os.listdir(dir_delete_4)
        for movie in movies_dir_delete_4:
            full_path = os.path.join(dir_delete_4,movie)
            logger.info(f"auto rate movie: {full_path}")
            number = get_number(movie)
            if number is None:
                continue
            auto_rate(db,number,"4")
            os.remove(full_path)
        
    if os.path.exists(dir_delete_5):
        movies_dir_delete_5 = os.listdir(dir_delete_5)
        for movie in movies_dir_delete_5:
            full_path = os.path.join(dir_delete_5,movie)
            logger.info(f"auto rate movie: {full_path}")
            number = get_number(movie)
            if number is None:
                continue
            auto_rate(db,number,"5")
            os.remove(full_path)

    # 测试，session保活
    if len(movies_dir_keep) == 0 and len(movies_dir_delete_4) == 0 and len(movies_dir_delete_5) == 0:
        db.session.get(f"{db.site}/users/want_watch_videos")
        
    db.save_cookies()
    logger.info("auto rate end.")

def add_list(db,number,list_id):
    '''添加到列表'''
    if list_id is None or list_id == "":
        return
    
    url = db.queryNumberUrl(number)
    videoid = url.rpartition('/')[-1]
    
    req_data = {
        "video_id":videoid,
        "checked":True,
        "list_id":list_id,
    }
    
    headers = {
        "Content-Type": "application/json",  # 关键头信息
        "Referer": url,
    }

    for i in range(5, -1, -1):
        try:
            response = db.session.post(f"{db.site}/users/save_video_to_list",json=req_data, headers=headers)
        except Exception as e:
            logger.error(f"retry save_video_to_list ... number:[{i}] info: {e}" )
            time.sleep(5)
    
    if '保持七天登入狀態' in response.text:
        logger.info(f"cookie out date!")
    else:
        logger.info(f"add list [{number}] response: [{response.status_code}] [{response.text}] ")
    
    interval = config.getIntValue("common.interval")
    if interval != 0:
        logger.info(f"Continue in {interval} seconds")
        time.sleep(interval)

    

def auto_rate(db,number,scope):
    url = db.queryNumberUrl(number)
    #requests.get(url)
    deatilpage = db.session.get(url).text
    if os.path.exists("./test.html"):
        os.remove("./test.html")

    htmltree = etree.fromstring(deatilpage, etree.HTMLParser())
    result = htmltree.xpath("//form[@id='new_review']")
    
    if result is None or len(result) == 0:
        result = htmltree.xpath("//form[@id='edit_review']")

    if result is None or len(result) == 0:
        print("error! see ./test.html")
        with open("./test.html", 'w', encoding='utf-8') as f:
            f.write(deatilpage)
        exit()

    form_tag = result[0]
    action_url = form_tag.get('action')
    authenticity_token = form_tag.find("input[@name='authenticity_token']").get('value')
    req_data = {
        "authenticity_token":authenticity_token,
        "video_review[status]":"watched",
        "video_review[score]":scope,
        "video_review[content]":"",
        "commit":"保存",
    }
    method = form_tag.find("input[@name='_method']")
    if method is not None:
        req_data["_method"] = method.get('value')

    for i in range(5, -1, -1):
        try:
            response = db.session.post(f"{db.site}{action_url}",data=req_data)
        except Exception as e:
            logger.error(f"retry... number:[{i}] info: {e}" )
            time.sleep(5)
    
    if '保持七天登入狀態' in response.text:
        logger.info(f"cookie out date!")
    else:
        logger.info(f"auto rate [{number}] response: [{response.status_code}] [{response.text}] ")
    
    interval = config.getIntValue("common.interval")
    if interval != 0:
        logger.info(f"Continue in {interval} seconds")
        time.sleep(interval)