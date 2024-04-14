import os
import re
import time
import requests
import wget
import pandas as pd
from bs4 import BeautifulSoup
from multiprocessing import Pool
from imageprocessor import ImageProcessor
from omegaconf import OmegaConf
from utils import remove_html_tags, html_table_to_markdown, get_table_tags

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

MAX_RETRIES = 3


class NoticeScraper:
    def __init__(self, args):
        self.args = args
        self.base_url = args.url
        self.num_workers = args.num_workers
        self.page_step = args.page_step
        self.df = None

        conf = OmegaConf.load("api_key.yaml")
        self.imgProcessor = ImageProcessor(
            conf["API_SECRET_KEY"], conf["OCR_URL"])

        if not os.path.exists('../datasets'):
            os.mkdir('../datasets')
        if not os.path.exists('../datasets/cache'):
            os.mkdir('cache')
        if not os.path.exists('../datasets/docs'):
            os.mkdir('docs')

    def scraping(self):
        for retry in range(MAX_RETRIES):
            try:
                self._scraping_routine()
                break
            except Exception as e:
                if retry == MAX_RETRIES - 1:
                    raise e
                print(
                    f"An error occurred during scraping: {e}. Retrying... (Retry {retry + 1}/{MAX_RETRIES})")

        file_name = self.base_url.split('/')[-1].split('.')[0]
        self.df.to_csv(f'../datasets/{file_name}.csv',
                       encoding='utf8', index=False)

    def _scraping_routine(self):
        file_name = self.base_url.split('/')[-1].split('.')[0]
        if os.path.exists(f'../datasets/cache/{file_name}_cache.csv'):
            self.df = pd.read_csv(
                f'../datasets/cache/{file_name}_cache.csv', encoding='utf8')
        else:
            self.df = pd.DataFrame(
                columns=['title', 'category', 'date', 'url', 'content'])

        total_page_step = self.page_step * self.num_workers
        page_num = max(len(self.df) - 10,
                       0) // total_page_step * total_page_step

        if page_num > 0:
            self.df = self.df[:page_num + 10]  # 겹치는 항목 제외

        while True:
            print(page_num)
            try:
                with Pool(4) as pool:
                    singleThread_dfs = pool.map(self.single_thread_scraping, [
                                                page_num + i * self.page_step for i in range(self.num_workers)])
                    pool.close()
                    pool.join()

            except Exception as e:
                print(f"An error occurred during multi-threading: {e}")
                raise e

            step_df = pd.DataFrame(
                columns=['title', 'category', 'date', 'url', 'content'])
            for sdf in singleThread_dfs:
                step_df = pd.concat([step_df, sdf])

            if len(step_df) == 0:
                break

            page_num += total_page_step
            self.df = pd.concat([self.df, step_df])
            self.df.reset_index(inplace=True, drop=True)
            self.df.to_csv(
                f'../datasets/cache/{file_name}_cache.csv', encoding='utf8', index=False)
        self.df.reset_index(inplace=True, drop=True)

    def single_thread_scraping(self, page_num):
        for retry in range(MAX_RETRIES):
            try:
                return self._single_thread_scraping_routine(page_num)
            except Exception as e:
                if retry == MAX_RETRIES - 1:
                    raise e
                print(
                    f"An error occurred during single thread scraping: {e}. Retrying... (Retry {retry + 1}/{MAX_RETRIES})")

    def _single_thread_scraping_routine(self, page_num):
        list_url = self.base_url + \
            f'?mode=list&&articleLimit={self.page_step}&article.offset={page_num}'
        response = requests.get(list_url)

        if response.status_code == 500:
            raise Exception(
                f"500 Internal Server Error for {list_url}. Maximum retries exceeded.")
        elif response.status_code != 200:
            raise Exception(
                f"Failed to fetch the page {list_url}. Status code: {response.status_code}")

        page_index = 10 if page_num != 0 else 0

        soup = BeautifulSoup(response.content, 'html.parser')
        title_tags = soup.select('table>tbody>tr>td.title>a')[page_index:]
        category_tags = soup.select('table>tbody>tr>td.category')[page_index:]
        date_tags = soup.select('table>tbody>tr>td.date')[page_index:]

        title_list = ['']*len(title_tags)
        category_list = ['']*len(category_tags)
        date_list = ['']*len(date_tags)
        url_list = ['']*len(title_tags)

        for idx, (title, category, date) in enumerate(zip(title_tags, category_tags, date_tags)):
            title_list[idx] = title.attrs['title']
            category_list[idx] = category.getText().strip()
            date_list[idx] = date.getText().strip()
            url_list[idx] = self.base_url + title.attrs['href']

        temp_df = pd.DataFrame({
            'title': title_list,
            'category': category_list,
            'date': date_list,
            'url': url_list
        })

        content_list = []
        for url in temp_df['url']:
            content = self.page_scraping(url)
            content_list.append(content)

        temp_df['content'] = content_list
        return temp_df

    def page_scraping(self, page_url):
        response = requests.get(page_url)
        soup = BeautifulSoup(response.content, 'html.parser')
        if self.args.docs:
            self.get_docs(soup)
        try:
            result = self.get_content(soup)
        except Exception as e:
            print("An error occurred during page scraping:", e)
            print(page_url)
            return ""
        return result

    def get_content(self, soup):
        content = soup.select(".board-contents")[0]
        tables = content.select(".board-contents table")
        tablesintables = content.select(".board-contents table table")
        tables[:] = [x for x in tables if x not in tablesintables]

        imgs = content.select(".board-contents img")
        content = str(content)

        for table in tables:
            markdown_table = html_table_to_markdown(table)
            s1, s2 = get_table_tags(content)
            content = content.replace(
                content[s1.start():s2.end()], markdown_table)

        for img in imgs:
            image_url = img.attrs['src']
            if re.search('cms/', image_url):
                if not re.search('https://www.kumoh.ac.kr/', image_url):
                    image_url = 'https://www.kumoh.ac.kr/'+img.attrs['src']

            s1 = re.search('<img[^>]+>', content)
            ocrText = self.imgProcessor.image_to_content(image_url)
            content = content.replace(content[s1.start():s1.end()], ocrText)

        content_text = remove_html_tags(content)
        return content_text

    def get_docs(self, soup):
        docs = soup.select("a.file-down-btn")
        for doc in docs:
            file_url = self.base_url + doc.attrs['href']
            file_name = f'./docs/{doc.getText().strip()}'
            if not os.path.exists(file_name):
                wget.download(file_url, out=file_name)


class ComputerEngineeringNoticeScraper(NoticeScraper):
    def __init__(self, args):
        super().__init__(args)

    def _scraping_routine(self):
        file_name = self.base_url.split('/')[-1].split('.')[0]
        if os.path.exists(f'../datasets/cache/{file_name}_cache.csv'):
            self.df = pd.read_csv(
                f'../datasets/cache/{file_name}_cache.csv', encoding='utf8')
        else:
            self.df = pd.DataFrame(
                columns=['title', 'date', 'url', 'content'])

        total_page_step = self.page_step * self.num_workers
        page_num = len(self.df) // total_page_step * total_page_step

        while True:
            print(page_num)
            try:
                with Pool(4) as pool:
                    singleThread_dfs = pool.map(self.single_thread_scraping, [
                                                page_num + i * self.page_step for i in range(self.num_workers)])
                    pool.close()
                    pool.join()

            except Exception as e:
                print(f"An error occurred during multi-threading: {e}")
                raise e

            step_df = pd.DataFrame(
                columns=['title', 'date', 'url', 'content'])
            for sdf in singleThread_dfs:
                step_df = pd.concat([step_df, sdf])

            if len(step_df) == 0:
                break

            page_num += total_page_step
            self.df = pd.concat([self.df, step_df])
            self.df.reset_index(inplace=True, drop=True)
            self.df.to_csv(
                f'../datasets/cache/{file_name}_cache.csv', encoding='utf8', index=False)
        self.df.reset_index(inplace=True, drop=True)

    def _single_thread_scraping_routine(self, page_num):
        list_url = self.base_url + \
            f'?mode=list&&articleLimit={self.page_step}&article.offset={page_num}'
        response = requests.get(list_url)

        if response.status_code == 500:
            raise Exception(
                f"500 Internal Server Error for {list_url}. Maximum retries exceeded.")
        elif response.status_code != 200:
            raise Exception(
                f"Failed to fetch the page {list_url}. Status code: {response.status_code}")

        soup = BeautifulSoup(response.content, 'html.parser')
        title_tags = soup.select('td.title.left')
        date_tags = soup.select('td.date')

        title_list = ['']*len(title_tags)
        date_list = ['']*len(date_tags)
        url_list = ['']*len(title_tags)

        for idx, (title, date) in enumerate(zip(title_tags, date_tags)):
            title_list[idx] = title.select_one(
                '.title-wrapper').getText().strip()
            date_list[idx] = date.getText().strip()
            url_list[idx] = self.base_url + title.a['href']

        temp_df = pd.DataFrame({
            'title': title_list,
            'date': date_list,
            'url': url_list
        })

        content_list = []
        for url in temp_df['url']:
            content = self.page_scraping(url)
            content_list.append(content)

        temp_df['content'] = content_list
        return temp_df


class FAQScraper:
    def __init__(self, args):
        self.args = args
        self.base_url = args.url
        self.num_workers = args.num_workers
        self.page_step = args.page_step
        self.df = None

    def scraping(self):
        page_num = 0
        self.df = pd.DataFrame(columns=['question', 'answer'])
        while (True):
            request_url = self.base_url + \
                f'?mode=list&&articleLimit={self.page_step}&article.offset={page_num}'
            response = requests.get(request_url
                                    )
            soup = BeautifulSoup(response.content, 'html.parser')
            temp_df = self.page_scraping(soup)
            self.df = pd.concat([self.df, temp_df])
            self.df.reset_index(drop=True, inplace=True)
            page_num += self.page_step
            if (len(temp_df) < self.page_step):
                break
        file_name = self.base_url.split('/')[-1].split('.')[0]
        self.df.to_csv(f'../datasets/{file_name}.csv',
                       encoding='utf8', index=False)

    def page_scraping(self, soup):
        question_list = []
        answer_list = []
        qna_pair = soup.select('div.faq-wrapper dl')
        for i in qna_pair:
            question = i.find('dt')
            answer = i.find('dd')

            question = self.get_content(question)
            answer = self.get_content(answer)

            question_list.append(question)
            answer_list.append(answer)

        df = pd.DataFrame({'question': question_list, 'answer': answer_list})
        return df

    def get_content(self, content):
        tables = content.select('table')
        content = str(content)
        for table in tables:
            markdown_table = html_table_to_markdown(table)
            s1, s2 = get_table_tags(content)
            content = content.replace(
                content[s1.start():s2.end()], markdown_table)

        content = remove_html_tags(content)
        return content


class GuideScraper(FAQScraper):
    def __init__(self, args):
        super().__init__(args)

    def scraping(self):
        self.df = pd.DataFrame(columns=['question', 'answer'])

        request_url = self.base_url
        response = requests.get(request_url
                                )
        soup = BeautifulSoup(response.content, 'html.parser')
        self.df = self.page_scraping(soup)
        self.df.reset_index(drop=True, inplace=True)

        file_name = self.base_url.split('/')[-1].split('.')[0]
        self.df.to_csv(f'../datasets/{file_name}.csv',
                       encoding='utf8', index=False)

    def page_scraping(self, soup):
        question_list = []
        answer_list = []
        qna_pair = soup.select('.contents-area dl')
        if len(qna_pair) != 0:
            for i in qna_pair:
                question = i.find('dt')
                answer = i.find('dd')

                question = self.get_content(question)
                answer = self.get_content(answer)

                question_list.append(question)
                answer_list.append(answer)

        else:
            contents = soup.select('.contents-area')
            for content in contents:
                title = content.find('h4').getText().strip()
                content_text = self.get_content(content)
                question_list.append(title)
                answer_list.append(content_text)

        df = pd.DataFrame(
            {'question': question_list, 'answer': answer_list})
        return df


class QnAScraper():
    def __init__(self, args):
        self.base_url = args.url
        self.LOGIN_INFO = OmegaConf.load('login_info.yaml')

        self.df = pd.DataFrame(columns=['title', 'date', 'question', 'answer'])

    def scraping(self):
        driver = webdriver.Chrome()

        # 페이지 접속 및 로그인
        self._login(driver)

        # 테이블의 제일 첫번째 요소 클릭
        self._first_element_click(driver)

        time.sleep(2)
        idx = 0
        while (True):
            try:
                # 각각의 요소 뽑아내기
                elements = self.get_value(driver)

                self.df.loc[idx] = elements
                idx += 1

                prev_title = driver.find_element(
                    by=By.XPATH, value='//*[@id="jwxe_main_content"]/div[2]/div/div[2]/a[1]/dl/dd').text

                if prev_title == "이전글이 없습니다.":
                    break

                # 이전 글로 넘어가기
                driver.find_element(
                    by=By.XPATH, value='//*[@id="jwxe_main_content"]/div[2]/div/div[2]/a[1]').click()
                time.sleep(3)
            except Exception:
                # 이전 글로 넘어가기
                driver.find_element(
                    by=By.XPATH, value='//*[@id="jwxe_main_content"]/div[2]/div/div[2]/a[1]').click()
                time.sleep(3)
                continue
        driver.quit()

        file_name = self.base_url.split('/')[-1].split('.')[0]
        self.df.to_csv(f'../datasets/{file_name}.csv',
                       encoding='utf8', index=False)

    def get_value(self, driver):
        url = driver.current_url
        title = driver.find_element(
            by=By.XPATH, value='//*[@id="jwxe_main_content"]/div[2]/div/div[1]/div[1]/div[1]').text
        date = driver.find_element(
            by=By.XPATH, value='//*[@id="jwxe_main_content"]/div[2]/div/div[1]/div[1]/div[2]/dl[3]/dd').text
        question = driver.find_element(
            by=By.XPATH, value='//*[@id="jwxe_main_content"]/div[2]/div/div[1]/div[1]/div[3]/pre').text
        answer = driver.find_element(
            by=By.CLASS_NAME, value='board-reply-txt.board-common-txt.ng-binding.ng-scope').text

        return {'title': title, 'date': date,
                'question': question, 'answer': answer, 'url': url}

    def _first_element_click(self, driver):
        driver.find_element(
            by=By.CSS_SELECTOR, value='#jwxe_main_content > div.contents-wrapper > div > div.board-list01 > table > tbody > tr:nth-child(1) > td.title.left > a').click()

    def _login(self, driver):
        driver.get(self.base_url)
        driver.find_element(
            by=By.XPATH, value='//*[@id="member_id"]').send_keys(self.LOGIN_INFO['ID'])  # id
        driver.find_element(
            by=By.XPATH, value='//*[@id="member_pw"]').send_keys(self.LOGIN_INFO['PW'])  # pw
        driver.find_element(
            by=By.XPATH, value='//*[@id="loginForm"]/fieldset/div/input').click()
        time.sleep(2)


class LibraryNoticeScraper():
    def __init__(self, args):
        self.base_url = args.url
        self.df = pd.DataFrame(columns=['title', 'date', 'content'])

    def scraping(self):
        driver = webdriver.Chrome()
        offset = 0
        EOF = False
        idx = 0

        while not EOF:
            # 페이지 접속
            url = self.base_url + f'?offset={offset}&max=20'
            driver.get(url)
            time.sleep(0.5)

            for i in range(20):
                if offset == 0:
                    element_xpath = f'//*[@id="content"]/div/div/div/div[2]/div/div[5]/table/tbody[2]/tr[{i+1}]/td[3]/span[2]/span/a'
                else:
                    element_xpath = f'//*[@id="content"]/div/div/div/div[2]/div/div[5]/table/tbody/tr[{i+1}]/td[3]/span[2]/span/a'

                try:
                    element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, element_xpath)))
                    element.click()
                    time.sleep(1)
                    self.scroll_down(driver)

                    soup_main = BeautifulSoup(
                        driver.page_source, 'html.parser')

                    try:
                        iframe = driver.find_element(
                            by=By.TAG_NAME, value=("iframe"))
                        driver.switch_to.frame(iframe)

                        # 페이지 소스를 가져와서 파싱
                        soup_frame = BeautifulSoup(
                            driver.page_source, 'html.parser')

                        # get_content(soup_frame)
                        # 원래 frame으로 돌아옵니다.
                        driver.switch_to.default_content()

                    except Exception as e:
                        print(f"오류 발생: {e}")
                        driver.switch_to.default_content()

                    title = soup_main.select_one(
                        '.ikc-bbsdetail-title').getText().strip()
                    date = soup_main.select(
                        '.ikc-bbsdetail-headerinfo span')[-1].getText().split()[0]
                    content = self.get_content(soup_frame)

                    self.df.loc[idx] = {'title': title,
                                        'date': date, 'content': content}
                    idx += 1
                    driver.back()  # 이전 페이지로 이동
                    time.sleep(1)

                except Exception as e:
                    print(f"오류 발생: {e}")
                    break
                    EOF = True

            offset += 20

        driver.quit()

        self.df.to_csv(f'../datasets/librarynotice.csv',
                       encoding='utf8', index=False)

    def get_content(self, soup):
        content = soup
        tables = content.select(".board-contents table")
        tablesintables = content.select(".board-contents table table")
        tables[:] = [x for x in tables if x not in tablesintables]
        content = str(content)

        for table in tables:
            markdown_table = html_table_to_markdown(table)
            s1, s2 = get_table_tags(content)
            content = content.replace(
                content[s1.start():s2.end()], markdown_table)

        content_text = remove_html_tags(content)
        return content_text

    def scroll_down(self, driver):
        before_h = driver.execute_script("return window.scrollY")
        while True:
            driver.find_element(by=By.CSS_SELECTOR, value=(
                "body")).send_keys(Keys.END)
            time.sleep(0.5)
            after_h = driver.execute_script("return window.scrollY")
            if after_h == before_h:
                break
            before_h = after_h
