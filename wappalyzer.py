import re
from get_data import GetData
from _common import IWebPage
from constants import CATEGORIES
from typing import Dict, Mapping, Set, Iterable
from fingerprint import Fingerprint, Technology, Category


class Wappalyzer:

    def __init__(self, force_update: bool = False):
        data = GetData().latest(force_update)
        categories = data['categories']
        technologies = data['technologies']

        self.categories: Mapping[str, Category] = {k: Category(**v) for k, v in categories.items()}
        self.technologies: Mapping[str, Fingerprint] = {k: Fingerprint(name=k, **v) for k, v in technologies.items()}
        self.detected_technologies: Dict[str, Dict[str, Technology]] = {}

        self._confidence_regexp = re.compile(r"(.+)\\;confidence:(\d+)")

    def _has_technology(self, tech_fingerprint: Fingerprint, webpage: IWebPage) -> bool:
        # analyze url patterns
        for pattern in tech_fingerprint.url:
            if pattern.regex.search(webpage.url):
                return True
        # analyze headers patterns
        for name, patterns in list(tech_fingerprint.headers.items()):
            if name in webpage.headers:
                content = webpage.headers[name]
                for pattern in patterns:
                    if pattern.regex.search(content):
                        return True
        # analyze scripts src patterns
        for pattern in tech_fingerprint.scriptSrc:
            for script in webpage.scripts:
                if pattern.regex.search(script):
                    return True
        # analyze meta patterns
        for name, patterns in list(tech_fingerprint.meta.items()):
            if name in webpage.meta:
                content = webpage.meta[name]
                for pattern in patterns:
                    if pattern.regex.search(content):
                        return True
        # analyze html patterns
        for pattern in tech_fingerprint.html:
            if pattern.regex.search(webpage.html):
                return True
        # analyze dom patterns
        # css selector, list of css selectors, or dict from css selector to dict with some of keys:
        #           - "exists": "": only check if the selector matches somthing, equivalent to the list form.
        #           - "text": "regex": check if the .innerText property of the element that matches the css selector matches the regex (with version extraction).
        #           - "attributes": {dict from attr name to regex}: check if the attribute value of the element that matches the css selector matches the regex (with version extraction).
        for selector in tech_fingerprint.dom:
            for item in webpage.select(selector.selector):
                if selector.exists:
                    return True
                if selector.text:
                    for pattern in selector.text:
                        if pattern.regex.search(item.inner_html):
                            return True
                if selector.attributes:
                    for attrname, patterns in list(selector.attributes.items()):
                        _content = item.attributes.get(attrname)
                        if isinstance(_content, str) or type(_content) == int:
                            for pattern in patterns:
                                if pattern.regex.search(_content):
                                    return True
        return False

    def _get_implied_technologies(self, detected_technologies: Iterable[str]) -> Iterable[str]:

        def __get_implied_technologies(technologies: Iterable[str]) -> Iterable[str]:
            _implied_technologies = set()
            for tech in technologies:
                try:
                    for implie in self.technologies[tech].implies:
                        # If we have no doubts just add technology
                        if 'confidence' not in implie:
                            _implied_technologies.add(implie)

                        # Case when we have "confidence" (some doubts)
                        else:
                            try:
                                # Use more strict regexp (cause we have already checked the entry of "confidence")
                                # Also, better way to compile regexp one time, instead of every time
                                app_name, confidence = self._confidence_regexp.search(implie).groups()  # type: ignore
                                if int(confidence) >= 50:
                                    _implied_technologies.add(app_name)
                            except (ValueError, AttributeError):
                                pass
                except KeyError:
                    pass
            return _implied_technologies

        implied_technologies = __get_implied_technologies(detected_technologies)
        all_implied_technologies: Set[str] = set()

        # Descend recursively until we've found all implied technologies
        while not all_implied_technologies.issuperset(implied_technologies):
            all_implied_technologies.update(implied_technologies)
            implied_technologies = __get_implied_technologies(all_implied_technologies)

        return all_implied_technologies

    def analyze(self, webpage: IWebPage) -> Set[str]:
        detected_technologies = set()

        for tech_name, technology in list(self.technologies.items()):
            if self._has_technology(technology, webpage):
                detected_technologies.add(tech_name)
        detected_technologies.update(self._get_implied_technologies(detected_technologies))

        detected_category_ids = set()
        for tech_name in detected_technologies:
            if tech_name in self.technologies:
                detected_category_ids.update(self.technologies[tech_name].cats)

        return list(map(lambda x: CATEGORIES[x], filter(lambda x: x in CATEGORIES, detected_category_ids)))