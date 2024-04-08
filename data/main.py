import argparse
from scraper import NoticeScraper, FAQScraper

path_Scarper = {
    "sub06_01_01_01": "NoticeScraper",
    "sub06_01_01_03": "NoticeScraper",
    "sub02_03_02_01": "FAQScraper",
    "sub02_03_02_02": "FAQScraper",
    "sub02_03_02_03": "FAQScraper",
    "sub02_03_02_04": "FAQScraper",
}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", "-l", type=str,
                        help="data source url", required=True)
    parser.add_argument("--num_workers", "-n", type=int,
                        help="num_workers", default=1)
    parser.add_argument("--page_step", "-p", type=int,
                        help="page_step", default=10)
    parser.add_argument("--docs", "-d", action='store_true',
                        help="docs download")

    args = parser.parse_args()
    file_name = args.url.split('/')[-1].split('.')[0]

    s = globals()[path_Scarper[file_name]](args)
    s.scraping()
