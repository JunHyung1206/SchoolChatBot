import argparse
from noticescraper import NoticeScraper

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

    s = NoticeScraper(args)
    s.scraping()
