import os
import re
import requests
import wget
import argparse
import pandas as pd

from bs4 import BeautifulSoup


class Scraper:
    def __init__(self, args):
        self.args = args
        self.base_url = args.url
        self.df = None

        if not os.path.exists('cache'):
            os.mkdir('cache')
        if not os.path.exists('docs'):
            os.mkdir('docs')
        
    def scraping(self):
        file_name = self.base_url.split('/')[-1].split('.')[0]
        
        if os.path.exists(f'./cache/{file_name}_cache.csv'):
            self.df = pd.read_csv(f'./cache/{file_name}_cache.csv', encoding='utf8')
        else:
            self.df = pd.DataFrame(columns = ['title','category','date', 'url', 'content'])
        
        
        page_step = 10
        page_num = len(self.df)//page_step * page_step
        
        while(True):
            list_url = self.base_url + f'?mode=list&&articleLimit={page_step}&article.offset={page_num}'
            response = requests.get(list_url)

            if response.status_code != 200:
                print(response.status_code)
                continue

            page_index = 10 if page_num != 0 else 0

            soup = BeautifulSoup(response.content, 'html.parser')
            title_tags = soup.select('table>tbody>tr>td.title>a')[page_index:]
            category_tags = soup.select('table>tbody>tr>td.category')[page_index:]
            date_tags = soup.select('table>tbody>tr>td.date')[page_index:]

            # 마지막 페이지까지 긁은 경우
            if len(title_tags) < page_step:
                break

            # 공지사항은 제외
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
            
            # 각 page 크롤링
            
            content_list = []
            for url in temp_df['url']:
                content = self.page_crawling(url)
                content_list.append(content)
            
            temp_df['content'] = content_list
            
            # temp_df concat 후 후처리
            page_num += page_step
            self.df = pd.concat([self.df,temp_df])
            self.df.reset_index(inplace = True, drop=True)
            self.df.to_csv(f'./cache/{file_name}_cache.csv',encoding = 'utf8',index= True,index_label='id')
            
        self.df.reset_index(inplace = True, drop=True)
        
    def page_crawling(self, page_url):
        response = requests.get(page_url)
        soup = BeautifulSoup(response.content, 'html.parser')
        if self.args.docs:
            self.get_docs(soup)
        
        try:
            result = self.get_content(soup)
        except Exception as e:
            print(e, page_url)
            result = ""
        return result
    
    
    
    def html_table_to_markdown(self, table):
        rows = table.find_all('tr')

        markdown_table = ''

        if len(rows) == 1:
            cells = rows[0].find_all(['th', 'td'])
            if len(cells) == 1:
                return str(table)

        for idx, row in enumerate(rows):
            cells = row.find_all(['th', 'td'])
            row_data = [cell.get_text().strip() for cell in cells]
            markdown_table += '| ' + ' | '.join(row_data) + ' |\n'
            if idx == 0:
                markdown_table += '| ' + ':-- | ' * len(cells) + '\n'
        return markdown_table
    
    
    def get_content(self, soup):
        content = soup.select(".board-contents")[0] # string 내용 뽑기
        # table 찾기
        tables = content.select(".board-contents table")
        
        content = str(content)
        
        for table in tables:
            markdown_table = self.html_table_to_markdown(table)
            s1 = re.search('<table[^>]+>',content)
            s2 = re.search('</table>',content)
            content = content.replace(content[s1.start():s2.end()], markdown_table)


        # p 태그 처리
        html_text = re.sub(r'<p\s*>', '', content)
        html_text = re.sub(r'</p\s*>', '\n', html_text)

        # br 태그 처리
        html_text = re.sub(r'<br\s*/?\s*>', '\n', html_text)

        # 나머지 태그 처리
        content_text = BeautifulSoup(html_text, 'html.parser').getText(separator=" ")


        # 이후 후처리
        content_text = re.sub(r'\xa0+',' ',content_text)
        content_text = re.sub(r'\r?\n *','\n',content_text)
        content_text = re.sub(r'\n *\n+','\n\n',content_text)
        content_text = re.sub(r'\ +',' ',content_text).strip()

        return content_text
    
    def get_docs(self, soup):
        docs = soup.select("a.file-down-btn")
        for doc in docs:
            file_url = self.base_url + doc.attrs['href']
            file_name = f'./docs/{doc.getText().strip()}'
            if not os.path.exists(file_name):
                wget.download(file_url, out=file_name)





if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--url","-l", type=str, help="please source url", required=True)
    parser.add_argument("--docs", "-d", action='store_true', help="docs download")
    
    args = parser.parse_args()
    
    s = Scraper(args)
    s.scraping()