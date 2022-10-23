import time
import requests
from Wappalyzer.Wappalyzer import Wappalyzer
from Wappalyzer import WebPage

wappalyzer = Wappalyzer(force_update=False)
response = requests.get('https://autovicity.com')

webpage = WebPage.new_from_response(response)
start_time = time.time()
result = wappalyzer.analyze(webpage)
print("--- %s seconds ---" % (time.time() - start_time))
print(result)
