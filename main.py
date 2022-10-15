import time
import requests
from Wappalyzer import Wappalyzer
from Wappalyzer.webpage import WebPage

wappalyzer = Wappalyzer(force_update=False)
response = requests.get('https://w3schools.com')

webpage = WebPage.new_from_response(response)
start_time = time.time()
result = wappalyzer.analyze_with_categories(webpage)
print("--- %s seconds ---" % (time.time() - start_time))
print(result)