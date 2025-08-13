# -*- coding: utf-8 -*-

import re
import os
import json
import requests
from urllib.parse import urljoin
from lxml import etree
from utils.httprequest import request_session
from ..parser import Parser
from .storyline import getStoryline

import config


class Javdb(Parser):
    source = 'javdb'

    expr_number = '//strong[contains(text(),"番號")]/../span/text()'
    expr_number2 = '//strong[contains(text(),"番號")]/../span/a/text()'
    expr_title = "/html/head/title/text()"
    expr_title_no = '//*[contains(@class,"movie-list")]/div/a/div[contains(@class, "video-title")]/text()'
    expr_runtime = '//strong[contains(text(),"時長")]/../span/text()'
    expr_runtime2 = '//strong[contains(text(),"時長")]/../span/a/text()'
    expr_uncensored = '//strong[contains(text(),"類別")]/../span/a[contains(@href,"/tags/uncensored?") or contains(@href,"/tags/western?")]'
    expr_actor = '//span[@class="value"]/a[contains(@href,"/actors/")]/text()'
    expr_actor2 = '//span[@class="value"]/a[contains(@href,"/actors/")]/../strong/@class'
    expr_release = '//strong[contains(text(),"日期")]/../span/text()'
    expr_release_no = '//*[contains(@class,"movie-list")]/div/a/div[contains(@class, "meta")]/text()'
    expr_studio = '//strong[contains(text(),"片商")]/../span/a/text()'
    expr_studio2 = '//strong[contains(text(),"賣家:")]/../span/a/text()'
    expr_director = '//strong[contains(text(),"導演")]/../span/text()'
    expr_director2 = '//strong[contains(text(),"導演")]/../span/a/text()'
    expr_cover = "//div[contains(@class, 'column-video-cover')]/a/img/@src"
    expr_cover2 = "//div[contains(@class, 'column-video-cover')]/img/@src"
    expr_cover_no = '//*[contains(@class,"movie-list")]/div/a/div[contains(@class, "cover")]/img/@src'
    expr_trailer = '//span[contains(text(),"預告片")]/../../video/source/@src'
    expr_extrafanart = "//article[@class='message video-panel']/div[@class='message-body']/div[@class='tile-images preview-images']/a[contains(@href,'/samples/')]/@href"
    expr_tags = '//strong[contains(text(),"類別")]/../span/a/text()'
    expr_tags2 = '//strong[contains(text(),"類別")]/../span/text()'
    expr_series = '//strong[contains(text(),"系列")]/../span/text()'
    expr_series2 = '//strong[contains(text(),"系列")]/../span/a/text()'
    expr_label = '//strong[contains(text(),"系列")]/../span/text()'
    expr_label2 = '//strong[contains(text(),"系列")]/../span/a/text()'
    expr_userrating = '//span[@class="score-stars"]/../text()'
    expr_uservotes = '//span[@class="score-stars"]/../text()'
    expr_actorphoto = '//strong[contains(text(),"演員:")]/../span/a[starts-with(@href,"/actors/")]'

    def __init__(self, _session = None):
        super(Javdb, self).__init__()
        self.fixstudio = False
        self.noauth = False
        self.site = config.getStrValue("overGFW."+self.source)
        if self.site is None:
            self.site = 'https://javdb.com/'
        self.number = ''
        self.session = _session if _session is not None else request_session(cookies=self.get_cookies())

    @staticmethod
    def get_cookies():
        if os.path.isfile("javdb.cookies"):
            with open('javdb.cookies', 'r') as f:
                return json.load(f)
        else:
            return {'over18':'1', 'theme':'auto', 'locale':'zh'}
        
    @staticmethod
    def set_cookies(cookies):
        if os.path.isfile("javdb.cookies"):
            with open('javdb.cookies', 'r+') as f:
                jsonstr = json.dumps(cookies, indent=4)
                f.seek(0)
                f.truncate()
                f.write(jsonstr)
    
    def save_cookies(self):
        cookies = requests.utils.dict_from_cookiejar(self.session.cookies)
        self.set_cookies(cookies)

    def search(self, number: str):
        self.number = number
        self.detailurl = self.queryNumberUrl(number)
        return self.get_from_detail_url(self.detailurl)
    
    def get_from_detail_url(self, detailurl:str):
        if detailurl is not None:
            self.detailurl = detailurl

        deatilpage = self.session.get(self.detailurl).text
        if '此內容需要登入才能查看或操作' in deatilpage or '需要VIP權限才能訪問此內容' in deatilpage:
            self.noauth = True
            self.imagecut = 0
            return self.dictformat(None)
        else:
            htmltree = etree.fromstring(deatilpage, etree.HTMLParser())
            return self.dictformat(htmltree)

    def queryNumberUrl(self, number):
        javdb_url = self.site + 'search?q=' + number + '&f=all'
        try:
            resp = self.session.get(javdb_url)
        except Exception as e:
            #print(e)
            raise Exception(f'[!] {number}: page not fond in javdb')

        self.querytree = etree.fromstring(resp.text, etree.HTMLParser()) 
        # javdb sometime returns multiple results,
        # and the first elememt maybe not the one we are looking for
        # iterate all candidates and find the match one
        urls = self.getTreeAll(self.querytree, '//*[contains(@class,"movie-list")]/div/a/@href')
        # 记录一下欧美的ids  ['Blacked','Blacked']
        if re.search(r'[a-zA-Z]+\.\d{2}\.\d{2}\.\d{2}', number):
            correct_url = urls[0]
        else:
            ids = self.getTreeAll(self.querytree, '//*[contains(@class,"movie-list")]/div/a/div[contains(@class, "video-title")]/strong/text()')
            try:
                self.queryid = ids.index(number)
                correct_url = urls[self.queryid]
            except:
                # 为避免获得错误番号，只要精确对应的结果
                if ids[0].upper() != number.upper():
                    raise ValueError("number not found in javdb")
                correct_url = urls[0]
        return urljoin(resp.url, correct_url)

    def getNum(self, htmltree):
        if self.noauth:
            return self.number
        # 番号被分割开，需要合并后才是完整番号
        part1 = self.getTreeElement(htmltree, self.expr_number)
        part2 = self.getTreeElement(htmltree, self.expr_number2)
        dp_number = part2 + part1
        # NOTE 检测匹配与更新 self.number
        if self.number != '' and dp_number.upper() != self.number.upper():
            raise Exception(f'[!] {self.number}: find [{dp_number}] in javdb, not match')
        self.number = dp_number
        return self.number

    def getTitle(self, htmltree):
        if self.noauth:
            return self.getTreeElement(htmltree, self.expr_title_no, self.queryid)
        browser_title = super().getTitle(htmltree)
        title = browser_title[:browser_title.find(' | JavDB')].strip()
        return title.replace(self.number, '').strip()

    def getCover(self, htmltree):
        if self.noauth:
            return self.getTreeElement(htmltree, self.expr_cover_no, self.queryid)
        return super().getCover(htmltree)

    def getRelease(self, htmltree):
        if self.noauth:
            return self.getTreeElement(htmltree, self.expr_release_no, self.queryid).strip()
        return super().getRelease(htmltree)

    def getDirector(self, htmltree):
        return self.getTreeElementbyExprs(htmltree, self.expr_director, self.expr_director2)
    
    def getSeries(self, htmltree):
        # NOTE 不清楚javdb是否有一部影片多个series的情况，暂时保留
        results = self.getTreeAllbyExprs(htmltree, self.expr_series, self.expr_series2)
        result = ''.join(results)
        if not result and self.fixstudio:
            result = self.getStudio(htmltree)
        return result

    def getLabel(self, htmltree):
        results = self.getTreeAllbyExprs(htmltree, self.expr_label, self.expr_label2)
        result = ''.join(results)
        if not result and self.fixstudio:
            result = self.getStudio(htmltree)
        return result

    def getActors(self, htmltree):
        actors = self.getTreeAll(htmltree, self.expr_actor)
        genders = self.getTreeAll(htmltree, self.expr_actor2)
        r = []
        idx = 0
        # NOTE only female, we dont care others
        actor_gendor = 'female'
        for act in actors:
            if((actor_gendor == 'all')
            or (actor_gendor == 'both' and genders[idx] in ['symbol female', 'symbol male'])
            or (actor_gendor == 'female' and genders[idx] == 'symbol female')
            or (actor_gendor == 'male' and genders[idx] == 'symbol male')):
                r.append(act)
            idx = idx + 1
        if re.match(r'FC2-[\d]+', self.number, re.A) and not r:
            r = '素人'
            self.fixstudio = True
        return r

    def getOutline(self, htmltree):
        return getStoryline(self.number, self.getUncensored(htmltree))

    def getTrailer(self, htmltree):
        video = super().getTrailer(htmltree)
        # 加上数组判空
        if video:
            if not 'https:' in video:
                video_url = 'https:' + video
            else:
                video_url = video
        else:
            video_url = ''
        return video_url

    def getTags(self, htmltree):
        return self.getTreeAllbyExprs(htmltree, self.expr_tags, self.expr_tags2)

    def getUserRating(self, htmltree):
        try:
            numstrs = self.getTreeElement(htmltree, self.expr_userrating)
            nums = re.findall('[0-9.]+', numstrs)
            return float(nums[0])
        except:
            return ''

    def getUserVotes(self, htmltree):
        try:
            result = self.getTreeElement(htmltree, self.expr_uservotes)
            v = re.findall('[0-9.]+', result)
            return int(v[1])
        except:
            return ''

    def getaphoto(self, url, session):
        html_page = session.get(url).text
        img_url = re.findall(r'<span class\=\"avatar\" style\=\"background\-image\: url\((.*?)\)', html_page)
        return img_url[0] if img_url else ''

    def getActorPhoto(self, htmltree):
        actorall = self.getTreeAll(htmltree, self.expr_actorphoto)
        if not actorall:
            return {}
        actors = self.getActors(htmltree)
        actor_photo = {}
        for i in actorall:
            x = re.findall(r'/actors/(.*)', i.attrib['href'], re.A)
            if not len(x) or not len(x[0]) or i.text not in actors:
                continue
            # NOTE: https://c1.jdbstatic.com 会经常变动，直接使用页面内的地址获取
            # actor_id = x[0]
            # pic_url = f"https://c1.jdbstatic.com/avatars/{actor_id[:2].lower()}/{actor_id}.jpg"
            # if not self.session.head(pic_url).ok:
            try:
                pic_url = self.getaphoto(urljoin(self.site, i.attrib['href']), self.session)
                if len(pic_url):
                    actor_photo[i.text] = pic_url
            except:
                pass
        return actor_photo

    def getMagnet(self, htmltree):

        # magnet-name column is-four-fifths
        html_links = self.getTreeAll(htmltree, '//div[@class="magnet-name column is-four-fifths"]')
        re = []
        for html_link in html_links:
            try:
                re.append({
                    "name":html_link.xpath('./a/span[@class="name"]/text()')[0].strip(),
                    "link":html_link.xpath('./a/@href')[0].strip(),
                    "meta":html_link.xpath('./a/span[@class="meta"]/text()')[0].strip(),
                    "tags":html_link.xpath('./a/div/span/text()')
                })
            except Exception as e:
                print(e)
        return re

