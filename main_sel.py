import asyncio
import copy
import json
import re

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
from settings import GOLDEN_XYZ_AUTH, DRIVER_PATH
from socket import timeout
from threading import Thread, current_thread
from asyncio.exceptions import TimeoutError
from datetime import datetime


async def get_site(session, url, timeout1):
    try:
        async with session.get(url, timeout=timeout1) as resp:
            s = await resp.text()
            return s
    except RuntimeError:
        print('Истекло время ожидания...')
        return ""


async def parse_page(title, text, url) -> bool:
    try:
        try:
            req = request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            html = request.urlopen(req, timeout=30).read()
            soup = BeautifulSoup(html, features="html.parser")
            hrefs = soup.find_all('a', href=True)
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
            for link in hrefs:
                if link.get('href').count('http') == 1 and link.get('href')[0] == 'h':  # and validators.url(link)
                    links.add(link.get('href'))
            #print(links)
            pages = [soup.text.lower()]
            #pages.append(BeautifulSoup(request.urlopen(request.Request(r'https://fantoken.com/inter/', headers={'User-Agent': 'Mozilla/5.0'})).read(),
            #                           features="html.parser").text.lower())
            count = 0
            same_timeout = set()
        except Exception as ex:
            print('Ошибка при парсинге первого сайта,', ex)
            return False
        if len(links) >= 100:
            return False
        pages = [soup.text.lower()]
        if 'https://www.wikidata.org/wiki/' not in url:
            async with aiohttp.ClientSession() as session:
                tasks = []
                for link in links:
                    count += 1
                    print(link, round((count / len(links)) * 100, 2), '%')
                    time_out1 = 15
                    try:
                        #if 'apk' not in link and 'pdf' not in link and '.png' not in link and '.mp4' not in link and '.jpg' not in link:
                        if link.find('.apk') == -1 or link.find('.pdf') == -1 or link.find('.mp4') == -1 or link.find('.png') == -1 or link.find('.jpg') == -1:
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
            return check_pages(pages, query)
        except Exception as ex:
            print('Ошибка при мультипоточной обработке сайтов,', ex)
            return False
    except Exception as e:
        print('Ошибка в функции parse_page: ', e)
        return False


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
    elif mx_precent >= 69.65:
        return True


async def fetch_async_patent(session, url, headers, body):
    async with session.post(url, headers=headers, data=json.dumps(body)) as resp:
        return await resp.text()


async def check_patent_date(patent_id, p_date):
    async with aiohttp.ClientSession() as session:
        headers = {
            "accept": "*/*",
            "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "content-type": "application/json; charset=UTF-8",
            "sec-ch-ua": "\"Not_A Brand\";v=\"99\", \"Google Chrome\";v=\"109\", \"Chromium\";v=\"109\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-requested-with": "XMLHttpRequest"
        }
        body = {
            "start": 0,
            "pageCount": 500,
            "sort": "date_publ desc",
            "docFamilyFiltering": "familyIdFiltering",
            "searchType": 1,
            "familyIdEnglishOnly": True,
            "familyIdFirstPreferred": "US-PGPUB",
            "familyIdSecondPreferred": "USPAT",
            "familyIdThirdPreferred": "FPRS",
            "showDocPerFamilyPref": "showEnglish",
            "queryId": 0,
            "tagDocSearch": False,
            "query": {
                "caseId": 2314024,
                "hl_snippets": "2",
                "op": "OR",
                "q": "\"{}\"".format(patent_id),
                "queryName": "\"{}\"".format(patent_id),
                "highlights": "1",
                "qt": "brs",
                "spellCheck": False,
                "viewName": "tile",
                "plurals": True,
                "britishEquivalents": True,
                "databaseFilters": [
                    {
                        "databaseName": "US-PGPUB",
                        "countryCodes": []
                    },
                    {
                        "databaseName": "USPAT",
                        "countryCodes": []
                    },
                    {
                        "databaseName": "USOCR",
                        "countryCodes": []
                    }
                ],
                "searchType": 1,
                "ignorePersist": True,
                "userEnteredQuery": "\"{}\"".format(patent_id)
            }
        }
        url = "https://ppubs.uspto.gov/dirsearch-public/searches/searchWithBeFamily"
        response = await fetch_async_patent(session, url, headers, body)
        x = json.loads(response)['patents']
        for _ in x:
            number_string = [x for x in re.split("[^\d]+", _['guid']) if x][0]
            number = number_string
            if number == patent_id or (patent_id.find('D') != -1 and _['guid'].find(patent_id) != -1):
                #print(_)
                #print(_['datePublished'])
                date_string = _['datePublished']
                parsed_date = datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%SZ")
                day = parsed_date.strftime("%d")
                day = int(day)
                formatted_date = parsed_date.strftime("%B %d, %Y").replace("0" + str(day), str(day))
                print(formatted_date)
                print('Сравнение дат патента:')
                symb = '!='
                if formatted_date == p_date:
                    symb = '=='
                    print(formatted_date, symb, p_date)
                    return True
                else:
                    print(formatted_date, symb, p_date)
                    return False
        return False


async def main() -> None:
    translator = Translator()
    golden_verification_url = 'https://dapp.golden.xyz/verification'
    chr_options = Options()
    chr_options.add_experimental_option("detach", True)
    _service = Service(DRIVER_PATH)
    drivers = []
    for _ in range(len(GOLDEN_XYZ_AUTH)):
        driver = webdriver.Chrome(service=_service)
        driver.set_window_size(1440, 900)
        driver.get(golden_verification_url)
        driver.delete_all_cookies()
        driver.execute_script('window.localStorage.clear();')
        driver.add_cookie({"name": "Golden_xyz_auth", "value": GOLDEN_XYZ_AUTH[_]})
        driver.refresh()
        drivers.append(driver)
    last = [""] * len(GOLDEN_XYZ_AUTH)
    links = [[]] * len(GOLDEN_XYZ_AUTH)
    while True:
        pass
    while True:
        for _ in range(len(GOLDEN_XYZ_AUTH)):
            try:
                driver = drivers[_]
                link = "https://gzmland.ru/"
                title = ""
                text = ""
                only_text = False
                try:
                    but = driver.find_element(By.XPATH, '/html/body/div[2]/div/div/div/div[2]/button')
                    try:
                        but.click()
                    except Exception as ex:
                        pass
                except Exception:
                    pass
                try:
                    link = driver.find_element(By.XPATH, '/html/body/div[1]/div[2]/main/div/div[1]/div[2]/div[3]/div/div/a').text
                    if 'http' not in link:
                        if 'Q' in link:
                            try:
                                link = driver.find_element(By.XPATH, '/html/body/div[1]/div[2]/main/div/div[1]/div[2]/div[3]/div/div/a').get_attribute('href')
                            except NoSuchElementException as ex:
                                print('Не удалось получить ссылку с индефикатором Q: ', ex)
                        else:
                            try:
                                link = driver.find_element(By.XPATH, '/html/body/div[1]/div[2]/main/div/div[1]/div[2]/div[3]/div/div/a').get_attribute('href')
                            except NoSuchElementException as ex:
                                print('Не удалось получить ссылку при помощи href ', ex)
                except NoSuchElementException as ex:
                    try:
                        link = driver.find_element(By.XPATH, '/html/body/div/div[2]/main/div/div[1]/div[2]/div[3]/div/div/span').text
                        if link.find('http') == -1:
                            only_text = True
                    except NoSuchElementException:
                        try:
                            mid = driver.find_element(By.XPATH, '/html/body/div[1]/div[2]/main/div/div[1]/div[2]/div[2]/div[1]/div[2]').text
                            if mid == 'Is a':
                                only_text = True
                        except NoSuchElementException as ex:
                          print('Не удалось определить тип')
                try:
                    title = driver.find_element(By.XPATH, '/html/body/div/div[2]/div[2]/div/div[1]/div[2]/div[1]/div/div[1]/h2/a').text
                except NoSuchElementException as ex:
                    driver.refresh()
                    print('Не удалось найти title:', ex)
                try:
                    text = driver.find_element(By.XPATH, '/html/body/div/div[2]/main/div/div[1]/div[2]/div[1]/div/div[2]/div').text
                except NoSuchElementException as ex:
                    driver.refresh()
                    print('Не удалось найти text:', ex)

                # Перевод текста на английский:
                #
                #if len(title) > 0:
                #    try:
                #        title = translator.translate(title).text
                #    except Exception as ex:
                #        print('Ошибка: ', ex)
                #if len(text) > 0:
                #    try:
                #        text = translator.translate(text).text
                #    except Exception as ex:
                #        print('Ошибка: ', ex)

                try:
                    alert = driver.find_element(By.XPATH, '/html/body/div[2]/div/div/div/div[2]/div[2]/button[2]')
                    alert.click()
                    print('Уведомления успешно выключены')
                except NoSuchElementException as e:
                    pass
                response = False
                patent_application = False
                date_of_patent = False
                patent_ac = False
                skips = driver.find_element(By.XPATH, '/html/body/div/div[2]/div[2]/div/div[2]/form/fieldset/div[3]/button').text
                #try:
                #    x = driver.find_element(By.XPATH, '/html/body/div/div[2]/main/div/div[1]/div[2]/div[2]/div[1]/div[2]/a').text
                #    if x == 'Patent Application Number ↗':
                #        us_patent = True
                #        try:
                #            x = driver.find_element(By.XPATH, '/html/body/div/div[2]/main/div/div[1]/div[3]/div[2]/div/a').text
                #            if x.find('http') != -1:
                #                patent_ac = True
                #            else:
                #                patent_ac = False
                #        except NoSuchElementException:
                #            patent_ac = False
                #        print('Patent Application Number', patent_ac)
                #except NoSuchElementException:
                #    pass
                try:
                    x = driver.find_element(By.XPATH, '/html/body/div[1]/div[2]/main/div/div[1]/div[2]/div[2]/div[1]/div[2]/a').text
                    if x == 'Date of Patent ↗':
                        date_of_patent = True
                    else:
                        date_of_patent = False
                except NoSuchElementException:
                    pass
                is_object = False
                try:
                    x = driver.find_element(By.XPATH, '/html/body/div/div[2]/main/div/div[1]/div[2]/div[3]/div/div[1]/h2/a/div').text
                    if len(x) > 0:
                        is_object = True
                except NoSuchElementException:
                    is_object = False
                skip = False
                school = False
                try:
                    x = driver.find_element(By.XPATH, '/html/body/div[1]/div[2]/main/div/div[1]/div[2]/div[1]/div/div[1]/h2/a/div').text
                    if x.find('chool') != -1:
                        school = True
                except NoSuchElementException:
                    pass
                if school:
                    response = False
                elif is_object:
                    response = True
                    print('Обьект')
                elif patent_application:
                    pass
                elif date_of_patent:
                    x = '_'
                    print('Зашли в патент')
                    try:
                        x = driver.find_element(By.XPATH, '/html/body/div[1]/div[2]/main/div/div[1]/div[2]/div[1]/div/div[1]/h2/a/div').text
                    except NoSuchElementException:
                        pass
                    if len(x) > 1:
                        patent_id = re.search(r'\b([A-Za-z]+\d+)\b', x)
                        if patent_id is None:
                            patent_id = re.search(r'\b\d+\b', x).group()
                        else:
                            patent_id = patent_id.group(1)
                        patent_id = re.sub(r'\b0+(\d+)', r'\1', patent_id)
                        response = await check_patent_date(patent_id, link)
                    else:
                        response = False
                elif link.find('linkedin.com') != -1 or link.find('angel.co') != -1 or link.find('discord.gg') != -1:
                    response = True
                elif only_text:
                    if not link.isdigit():
                        response = True
                        print('Текстовый вопрос - ', response)
                    else:
                        response = True
                        print('Текстовый вопрос - ', response)
                else:
                    print('Ссылка - ', link)
                    response = await parse_page(title, text, link)
                    if response is None:
                        response = False
                if skip:
                    try:
                        x = driver.find_element(By.XPATH, '/html/body/div/div[2]/main/div/div[2]/form/fieldset/div[3]/button')
                        x.click()
                        print('US-Patent Скип', skips)
                    except NoSuchElementException:
                        pass
                elif response:
                    print(response)
                    try:
                        accept_button = driver.find_element(By.XPATH, '/html/body/div/div[2]/main/div/div[2]/form/fieldset/div[1]/button')
                        accept_button.click()
                    except NoSuchElementException as e:
                        try:
                            alert = driver.find_element(By.XPATH, '/html/body/div[2]/div/div/div/div[2]/div[2]/button[2]')
                            alert.click()
                            print('Уведомления успешно выключены')
                        finally:
                            pass
                else:
                    print(response)
                    try:
                        reject_button = driver.find_element(By.XPATH, '/html/body/div/div[2]/main/div/div[2]/form/fieldset/div[2]/button')
                        reject_button.click()
                    except NoSuchElementException as e:
                        try:
                            alert = driver.find_element(By.XPATH, '/html/body/div[2]/div/div/div/div[2]/div[2]/button[2]')
                            alert.click()
                            print('Уведомления успешно выключены')
                        finally:
                            pass
                await asyncio.sleep(4)
                links[_].append(link)
                if last[_] == link or (len(links[_]) >= 3 and links[_][-1] == links[_][-2] and links[_][-2] == links[_][-3]):
                    driver.refresh()
                last[_] = link
            except Exception as ex:
                print('Глобальный выход', ex)

if __name__ == "__main__":
    try:
        start_time = time.time()
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
        print("--- %s seconds ---" % (time.time() - start_time))
    finally:
        #os.system('fix.py')
        pass
