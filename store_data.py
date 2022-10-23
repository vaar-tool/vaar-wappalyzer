import requests
from typing import Dict, Any
from constants import CATEGORIES

class StoreData:
    def get_latest_tech_data(self) -> Dict[str, Any]:
        cats = requests.get('https://github.com/AliasIO/wappalyzer/raw/master/src/categories.json').json()
        techs: Dict[str, Any] = {}
        for _ in '_abcdefghijklmnopqrstuvwxyz':
            r = requests.get(f'https://github.com/AliasIO/wappalyzer/raw/master/src/technologies/{_}.json')
            techs = {**techs, **r.json()}
        obj = {'categories': cats, 'technologies': techs}
        obj = self.__filter_needed_data(obj)
        return obj

    def __filter_needed_data(self, data) -> Dict[str, Any]:
        needed_categories = CATEGORIES.keys()

        categories = {}
        for category_id in needed_categories:
            categories[category_id] = data['categories'][str(category_id)]

        technologies = {}
        for key in data['technologies']:
            intersection = set(data['technologies'][key]['cats']).intersection(set(needed_categories))
            if len(intersection):
                technologies[key] = data['technologies'][key]
        return {'categories': categories, 'technologies': technologies}
