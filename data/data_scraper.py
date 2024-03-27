import os
import re
import requests
import wget
import pandas as pd
from bs4 import BeautifulSoup
from multiprocessing import Pool
from utils import remove_html_tags, html_table_to_markdown

MAX_RETRIES = 3

class Scraper:
    def __init__(self, args):
        self.args = args
        self.base_url = args.url
        self.num_workers = args.num_workers
        self.page_step = args.page_step
        self.df = None

        if not os.path.exists('cache'):
            os.mkdir('cache')
        if not os.path.exists('docs'):
            os.mkdir('docs')

    def scraping(self):
        for retry in range(MAX_RETRIES):
            try:
                self._scraping_routine()
                break
            except Exception as e:
                if retry == MAX_RETRIES - 1:
                    raise e
                print(f"An error occurred during scraping: {e}. Retrying... (Retry {retry + 1}/{MAX_RETRIES})")

    def _scraping_routine(self):
        file_name = self.base_url.split('/')[-1].split('.')[0]
        if os.path.exists(f'./cache/{file_name}_cache.csv'):
            self.df = pd.read_csv(f'./cache/{file_name}_cache.csv', encoding='utf8')
        else:
            self.df = pd.DataFrame(columns=['title', 'category', 'date', 'url', 'content'])

        total_page_step = self.page_step * self.num_workers
        page_num = max(len(self.df) - 10, 0) // total_page_step * total_page_step

        if page_num > 0:
            self.df = self.df[:page_num + 10]  # 겹치는 항목 제외

        while True:
            print(page_num)
            try:
                with Pool(4) as pool:
                    singleThread_dfs = pool.map(self.single_thread_scraping,
                                                [page_num + i * self.page_step for i in range(self.num_workers)])
                    pool.close()
                    pool.join()

            except Exception as e:
                print(f"An error occurred during multi-threading: {e}")
                raise e

            step_df = pd.DataFrame(columns=['title', 'category', 'date', 'url', 'content'])
            for sdf in singleThread_dfs:
                step_df = pd.concat([step_df, sdf])

            if len(step_df) == 0:
                break

            page_num += total_page_step
            self.df = pd.concat([self.df, step_df])
            self.df.reset_index(inplace=True, drop=True)
            self.df.to_csv(f'./cache/{file_name}_cache.csv', encoding='utf8', index=False)
        self.df.reset_index(inplace=True, drop=True)

    def single_thread_scraping(self, page_num):
        for retry in range(MAX_RETRIES):
            try:
                return self._single_thread_scraping_routine(page_num)
            except Exception as e:
                if retry == MAX_RETRIES - 1:
                    raise e
                print(f"An error occurred during single thread scraping: {e}. Retrying... (Retry {retry + 1}/{MAX_RETRIES})")

    def _single_thread_scraping_routine(self, page_num):
        list_url = self.base_url + f'?mode=list&&articleLimit={self.page_step}&article.offset={page_num}'
        response = requests.get(list_url)

        if response.status_code == 500:
            raise Exception(f"500 Internal Server Error for {list_url}. Maximum retries exceeded.")
        elif response.status_code != 200:
            raise Exception(f"Failed to fetch the page {list_url}. Status code: {response.status_code}")

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
            'title':title_list,
            'category':category_list,
            'date' : date_list,
            'url' : url_list
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
        content = str(content)

        for table in tables:
            markdown_table = html_table_to_markdown(table)
            s1 = re.search('<table[^>]+>', content)
            s2 = re.search('</table>', content)
            content = content.replace(content[s1.start():s2.end()], markdown_table)

        content_text = remove_html_tags(content)
        return content_text
    

    def get_docs(self, soup):
        docs = soup.select("a.file-down-btn")
        for doc in docs:
            file_url = self.base_url + doc.attrs['href']
            file_name = f'./docs/{doc.getText().strip()}'
            if not os.path.exists(file_name):
                wget.download(file_url, out=file_name)