import argparse
from scraper import NoticeScraper, ComputerEngineeringNoticeScraper, FAQScraper, GuideScraper, QnAScraper, LibraryNoticeScraper

path_Scarper = {
    "sub02_03_02": "FAQScraper",
    "sub02_03_03": "GuideScraper",
    "sub02_03_04": "GuideScraper",
    "sub06_01_01": "NoticeScraper",
    "sub06_03_02": "QnAScraper",
    "sub0501": "ComputerEngineeringNoticeScraper",
    'notice': "LibraryNoticeScraper"
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

    if 'https://www.kumoh.ac.kr/' in args.url:
        category = '_'.join(file_name.split('_')[0:3])
    else:
        category = file_name
    s = globals()[path_Scarper[category]](args)
    s.scraping()
