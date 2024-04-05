import os
import re
import requests
import wget
import pandas as pd
from bs4 import BeautifulSoup
from omegaconf import OmegaConf

def remove_html_tags(html_text):
    # p 태그 처리
    html_text = re.sub(r'<p\s*>', '', html_text)
    html_text = re.sub(r'</p\s*>', '\n', html_text)

    # br 태그 처리
    html_text = re.sub(r'<br\s*/?\s*>', '\n', html_text)

    # 나머지 태그 처리
    content_text = BeautifulSoup(html_text, 'html.parser').getText(separator=" ")

    # 이후 후처리
    content_text = re.sub(r'\xa0+', ' ', content_text)
    content_text = re.sub(r'\r?\n *', '\n', content_text)
    content_text = re.sub(r'\n *\n+', '\n\n', content_text)
    content_text = re.sub(r'\ +', ' ', content_text).strip()

    return content_text

def html_table_to_markdown(table):
    rows = table.find_all('tr')

    markdown_table = ''

    for idx, row in enumerate(rows):
        cells = row.find_all(['th', 'td'])
        row_data = [cell.get_text().strip() for cell in cells]
        markdown_table += '| ' + ' | '.join(row_data) + ' |\n'
        if idx == 0:
            markdown_table += '| ' + ':-- | ' * len(cells) + '\n'
    return markdown_table
