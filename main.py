import asyncio
import copy
import json
import re
from _ast import keyword
import aiohttp
import time
import os
import validators
from urllib import request
from bs4 import BeautifulSoup
from googletrans import Translator
from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from settings import GOLDEN_XYZ_AUTH
from socket import timeout
from threading import Thread, current_thread
from asyncio.exceptions import TimeoutError
from datetime import datetime
import pandas as pd
import pymysql
import cryptography
import ssl


async def get_site(session, url, timeout1):
    try:
        async with session.get(url, timeout=timeout1, ssl=False) as resp:
            s = await resp.text()
            return s
    except RuntimeError:
        print('Истекло время ожидания...')
        return ""


async def parse_page_fetch(url):
    async with aiohttp.ClientSession() as session:
        headers = {'User-Agent': 'Mozilla/5.0'}
        async with session.get(url, headers=headers, timeout=10, ssl=False) as resp:
            html = await resp.text()
        soup = BeautifulSoup(html, features="html.parser")
        hrefs = soup.find_all('a', href=True)
        return [soup, hrefs]


async def parse_page(title, text, url, key, triple_id) -> list:
    try:
        try:
            if url.find('linkedin.com') != -1 or url.find('angel.co') != -1 or url.find('discord.gg') != -1:
                return [key, triple_id, True]
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            a = await parse_page_fetch(url)
            soup = a[0]
            hrefs = a[1]
            links = set()
            query = title.lower().split(" ") + text.lower().split(" ")
            if len(text) >= 50:
                query = title.lower().split(" ")
            q = 0
            while q < len(query):
                if len(query[q]) < 3 or query[q] in ['the', 'and', 'for']:
                    query.pop(q)
                    q -= 1
                q += 1
            print(query)
            if 'olympic' in query:
                return [key, triple_id, True]
            for link in hrefs:
                if link.get('href').count('http') == 1 and link.get('href')[0] == 'h':  # and validators.url(link)
                    links.add(link.get('href'))
            # print(links)
            pages = [soup.text.lower()]
            # pages.append(BeautifulSoup(request.urlopen(request.Request(r'https://fantoken.com/inter/', headers={'User-Agent': 'Mozilla/5.0'})).read(),
            #                           features="html.parser").text.lower())
            count = 0
            same_timeout = set()
        except Exception as ex:
            print('Ошибка при парсинге первого сайта,', ex)
            return [key, triple_id, False]
        if len(links) >= 100:
            return [key, triple_id, True]
        pages = [soup.text.lower()]
        if 'https://www.wikidata.org/wiki/' not in url and 1 == 0:
            async with aiohttp.ClientSession() as session:
                tasks = []
                for link in links:
                    count += 1
                    print(link, round((count / len(links)) * 100, 2), '%')
                    time_out1 = 10
                    try:
                        # if 'apk' not in link and 'pdf' not in link and '.png' not in link and '.mp4' not in link and '.jpg' not in link:
                        if link.find('.apk') == -1 or link.find('.pdf') == -1 or link.find('.mp4') == -1 or link.find(
                                '.png') == -1 or link.find('.jpg') == -1:
                            pass
                        else:
                            tasks.append(asyncio.ensure_future(get_site(session, link, time_out1)))
                            same_timeout.add(link.split('//')[1].split('/')[0])
                    except timeout:
                        same_timeout.add(link.split('//')[1].split('/')[0])
                        print('Ошибка: ', timeout)
                sites = await asyncio.gather(*tasks)
                for site in sites:
                    pages.append(BeautifulSoup(site, features="html.parser").text.lower())
        try:
            return [key, triple_id, check_pages(pages, query)]
        except Exception as ex:
            print('Ошибка при мультипоточной обработке сайтов,', ex)
            return [key, triple_id, False]
    except Exception as e:
        print('Ошибка в функции parse_page: ', e)
        return [key, triple_id, False]


def check_page(page, query):
    words = 0
    for word in query:
        if page.find(word[1:]) != -1:
            words += 1
        elif page.find(word[:-1]) != -1:
            words += 1
        elif page.find(word) != -1:
            words += 1
    if len(query) > 0:
        precent = words / len(query) * 100
    else:
        precent = 0
    thread = current_thread()
    thread.result = precent


def check_pages(pages, query):
    threads = []
    mx_precent = 0
    for page in pages:
        thread = Thread(target=check_page, args=(page, query))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
        mx_precent = max(mx_precent, thread.result)
    print(mx_precent, '%')
    if len(query) <= 5:
        if mx_precent >= 64.95:
            return True
        else:
            return False
    elif len(query) >= 9:
        if mx_precent >= 48.95:
            return True
        else:
            return False
    elif mx_precent >= 64.65:
        return True


async def fetch_async_patent(session, url, headers, body):
    try:
        async with session.post(url, headers=headers, data=json.dumps(body), ssl=False) as resp:
            #print(resp.status)
            #print(resp.headers)
            #print(await resp.text())
            return await resp.text()
    except Exception as ex:
        print('fetch_async_patent', ex)


async def check_patent(patent_id, p_date, type):
    async with aiohttp.ClientSession() as session:
        headers = {
            "accept": "application/json",
            "accept-language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7,ru;q=0.6",
            "sec-ch-ua": "\"Chromium\";v=\"110\", \"Not A(Brand\";v=\"24\", \"Google Chrome\";v=\"110\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"macOS\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin"
        }
        body = {
            "referrer": "https://assignment.uspto.gov/patent/index.html",
            "referrerPolicy": "strict-origin-when-cross-origin",
            "body": "null",
            "method": "GET",
            "mode": "cors",
            "credentials": "include"
        }
        url = 'https://assignment.uspto.gov/solr/aotw/select?fl=applNum,publNum,publDate,filingDate&fq=publNum:20220354340&q=*:*&rows=4'
        response = await fetch_async_patent(session, url, headers, body)
        print(json.loads(response))
        if response is not None:
            x = json.loads(response)['patents']
        else:
            x = []
        # May 1, 212 != May 1, 2012
        try:
            for _ in x:
                if type == 'date':
                    number_string = [x for x in re.split("[^\d]+", _['guid']) if x][0]
                    number = int(number_string)
                    if number_string == patent_id or (patent_id.find('D') != -1 and _['guid'].find(patent_id) != -1):
                        # print(_)
                        # print(_['datePublished'])
                        date_string = _['datePublished']
                        # print(date_string.split('T')[0])
                        date_string = date_string.split('T')[0]
                        # print('Сравнение дат патента:')
                        symb = '!='
                        if date_string == p_date:
                            symb = '=='
                            # print(date_string, symb, p_date)
                            return True
                        else:
                            # print(date_string, symb, p_date)
                            # return False
                            pass
                elif type == 'patent_application_number':
                    number_str = _['applicationNumber']
                    str = ''
                    for i in number_str:
                        if i.isdigit():
                            str += i
                    if str == p_date:
                        return True
                    else:
                        # return False
                        pass
                elif type == 'patent_number':
                    if _['publicationReferenceDocumentNumber'] == p_date:
                        return True
                    else:
                        # return False
                        pass
                elif type == 'date_field':
                    number_str = _['applicationFilingDate'][0]
                    if p_date == number_str.split('T')[0]:
                        return True
                    else:
                        # return False
                        pass
            return False
            # print('No patent result', patent_id, p_date)
        except Exception as ex:
            print('Parse_patent', ex)
        return False


# Добавить проверку aplitcation number
# applicationNumber:"17/260508"  => 17260508

async def fetch(key, type, verdict=False, triple_id=None):
    url = "https://dapp.golden.xyz/verification?_data=routes%2Fverification"
    headers = {
        "accept": "*/*",
        "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
        "sec-ch-ua": "\"Not_A Brand\";v=\"99\", \"Google Chrome\";v=\"109\", \"Chromium\";v=\"109\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin"
    }
    cookie = {
        "Golden_xyz_auth": key
    }
    if type == 'GET':
        async with aiohttp.ClientSession(cookies=cookie) as session:
            async with session.get(url=url, headers=headers, ssl=False) as resp:
                # print(resp.status)
                #print(await resp.text())
                return [await resp.text(), key]
    elif type == 'POST':
        if verdict:
            action = 'accept'
        else:
            action = 'reject'
        payload = "tripleId={}&_action={}".format(triple_id, action)
        # print(payload)
        async with aiohttp.ClientSession(cookies=cookie) as session:
            async with session.post(url=url, headers=headers, data=payload, ssl=False) as resp:
                # print(resp.status)
                return await resp.text()


async def async_fetch_patent(typee, name, value, key, triple_id):
    try:
        is_D = False
        pos = 0
        for K in range(len(name)):
            if name[K].isdigit():
                pos = K
                break
        str = ''
        try:
            while name[pos].isdigit():
                if pos > 0 and name[pos - 1] == 'D':
                    is_D = True
                str += name[pos]
                pos += 1
            patent_id = str
            patent_id = patent_id.lstrip('0')
            if is_D:
                patent_id = 'D' + patent_id
            verdict = await check_patent(patent_id, value, typee)
            return [key, triple_id, verdict]
        except Exception as ex:
            print('check_patent', ex)
    except Exception as ex:
        print('Asfepa', ex)
        return [key, triple_id, True]


async def fetch_True(key, triple_id):
    return [key, triple_id, True]


async def fetch_False(key, triple_id):
    return [key, triple_id, False]


async def fetch_bd(values, patents_queue, names_queue):
    global cursor
    names = ['Patent Number', 'Patent Application Number', 'Date Filed', 'Date of Patent', 'Patent Publication Code']
    print("d0")
    arrVal = values.split(", ")
    req = f"SELECT * FROM patents_db.patentsTable WHERE application_id IN ({'17734841'});"
    print("d1")
    cursor.execute(req)
    print("d2")
    rows = cursor.fetchall()
    print("d3")
    print(rows)
    #print("values: ", values)
    #print("patent",patents_queue)
    for row in rows:
        row = list(row)
        print(row)
        print(patents_queue[row[1]])
        print("////////////////////////////")
        data = names_queue[row[1]]
        print(data)
        ind = names.index(data[0])
        if data[1] == row[ind]:
            print("ok")
        else:

            print("ne ok")

global cursor


async def fetch_date(key, triple_id, value, date):
    #print("zalupa")
    headers = {
            "referrerPolicy": "strict-origin-when-cross-origin",
            "body": "null",
            "method": "GET",
            "mode": "cors",
            "credentials": "include"
        }
    url = f"https://assignment.uspto.gov/solr/aotw/select?fl=publDate,filingDate,issueDate&fq=applNum:{value}&hl=true&lowercaseOperators=true&q=*:*&rows=500&wt=json"
    async with aiohttp.ClientSession() as session:
        async with session.get(url=url, headers=headers, ssl=False) as resp:
            #print("//////////////////")
            #print(resp.status)
            data = await resp.json(content_type=None)
            #print("$$$$", data["response"], "$", type(date["response"]), "$$$$")
            if data["response"]["numFound"] == 0:
                return [key, triple_id, True]
            docs = data["response"]["docs"]
            for doc in docs:
                for _ in ["filingDate", "publDate", "issueDate"]:
                    for __ in doc[_]:
                        d = __.split("T")[0]
                        if d == date:
                            return [key, triple_id, True]
    return [key, triple_id, False]
            #return [await resp.text(), key]


async def main() -> None:
    db = pymysql.connect(
        host="localhost",
        user="root",
        password="21594121",
        database="patents_db",
    )
    global cursor
    cursor = db.cursor()
    table_name = 'patentsTable'
    golden_verification_url = 'https://dapp.golden.xyz/verification'
    keys = []
    for _ in range(len(GOLDEN_XYZ_AUTH)):
        keys.append(GOLDEN_XYZ_AUTH[_])
    last = [""] * len(GOLDEN_XYZ_AUTH)
    links = [[]] * len(GOLDEN_XYZ_AUTH)
    timer = 0
    count = 0
    sum_results = 0
    debug_time = True
    while True:
        try:
            start_time = time.time()
            verdicts = []
            gets = []
            take_gets = []
            t1 = time.time()
            for _ in range(len(GOLDEN_XYZ_AUTH)):
                key = keys[_]
                take_gets.append(fetch(key, 'GET'))
                # x = json.loads(await fetch(key, 'GET'))['payload']['statement']
                # gets.append([key, x])
            results = await asyncio.gather(*take_gets)
            if debug_time:
                print('1. GET троек -', round(time.time() - t1, 3), 'sec')
                t2 = time.time()
            number_ac = 0
            for i in results:
                x = None
                # print(i)
                number_ac += 1
                try:
                    x = json.loads(i[0])['payload']['statement']
                    gets.append([i[1], x])
                except Exception as ex:
                    print('X.loads.result account №{}'.format(number_ac), ex)
            # print('Gets:', gets)
            # print(x)
            # print(name)
            # print(middleValue)
            # print(value)
            verdicts_coroutine = []
            patents_queue = dict()
            names_queue = dict()
            values = ''
            uspot_col = 0
            database_col = 0
            for i in range(len(gets)):
                x = gets[i][1]
                key = gets[i][0]
                #x = i[1]
                #key = i[0]
                value = x['objectValue']
                triple_id = x['id']
                middleValue = x['predicate']['name']
                name = x['subject']['name']
                link = "https://gzmland.ru/"
                verdict = False
                is_D = False
                subject = x['subject']['statementsBySubjectId']['nodes']
                if value is None:
                    value = x['objectEntity']['name']
                    # verdict = True
                    verdicts_coroutine.append(fetch_True(key, triple_id))
                elif value.find('crickettimes') != -1:
                    verdicts_coroutine.append(fetch_False(key, triple_id))
                elif middleValue == "Patent Jurisdiction":#askkkkkksakdakdskakdksakdkasdkksdkaskdaksdkaksdkkdaksdkaskdkaskdaksdkaksdaksdkaks
                    verdicts_coroutine.append(fetch_True(key, triple_id))
                elif middleValue in ['Patent Application Number', 'Patent Number', 'Date Filed', 'Patent Publication Code']:
                    database_col += 1
                    """for node in subject:
                        val = node['objectValue']
                        n = node['predicate']['name']
                        if n == "Patent Application Number":
                            patents_queue[val] = key
                            names_queue[val] = [middleValue, value, key]
                            values += f"'{val}'"
                            if i + 1 < len(gets):
                                values += ', '
                            break"""
                    verdicts_coroutine.append(fetch_True(key, triple_id))
                elif middleValue == "Date of Patent":
                    uspot_col += 1
                    #print("ok")
                    val = 0
                    for node in subject:
                        val = node['objectValue']
                        #print("#####", val, "#####")
                        n = node['predicate']['name']
                        if n == "Patent Application Number":
                            break
                    verdicts_coroutine.append(fetch_date(key, triple_id, val, value))#key triple applNum date
                elif middleValue == 'Duplicate of':
                    print("ne ebu")
                    verdicts_coroutine.append(fetch_True(key, triple_id))
                elif value.find('http') != -1:
                    #verdicts_coroutine.append(parse_page(name, '', value, key, triple_id))
                    verdicts_coroutine.append(fetch_True(key, triple_id))
                else:
                    verdicts_coroutine.append(fetch_True(key, triple_id))
            #if len(values) > 0:
                #result = await fetch_bd(values, patents_queue, names_queue)
            #while 1:
               # pass
            #print("database -", database_col)
            #print("uspot -", uspot_col)
            verdict_results = await asyncio.gather(*verdicts_coroutine)
            if debug_time:
                print('2. Check -', round(time.time() - t2, 3), 'sec')
                t3 = time.time()
            #print(len(verdict_results))
            for _ in verdict_results:
                key = _[0]
                triple_id = _[1]
                verdict = _[2]
                if verdict:
                    verdicts.append([key, 'POST', verdict, triple_id])
                    # await fetch(key, 'POST', verdict, triple_id)
                else:
                    verdict = False
                    verdicts.append([key, 'POST', verdict, triple_id])
                    # await fetch(key, 'POST', verdict, triple_id)\
            coroutines = []
            for _ in verdicts:
                key, type_, verdict, triple_id = _[0], _[1], _[2], _[3]
                coroutines.append(fetch(key, type_, verdict, triple_id))
            results = await asyncio.gather(*coroutines)
            if debug_time:
                print('3. POST -', round(time.time() - t3, 3), 'sec')
            # print('Results:', results)
            timer += (time.time() - start_time)
            count += 1
            sum_results += len(results)
            print('Круг №', count, '| Проверено', sum_results, 'троек')
            print("--- %s seconds ---" % (timer / count))
            print('##################################')
        except Exception as ex:
            print('Глобальный выход', ex)


if __name__ == "__main__":
    try:
        print(123)
        start_time = time.time()
        asyncio.run(main())
        print("--- %s seconds ---" % round((time.time() - start_time), 3))
    finally:
        os.system('fix.py')
        # pass