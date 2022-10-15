import re
from typing import Optional
from get_data import GetData
from Wappalyzer.webpage import IWebPage
from typing import Callable, Dict, Iterable, List, Any, Mapping, Set
from Wappalyzer.fingerprint import Fingerprint, Pattern, Technology, Category


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
        has_tech = False
        # Search the easiest things first and save the full-text search of the
        # HTML for last

        # analyze url patterns
        for pattern in tech_fingerprint.url:
            if pattern.regex.search(webpage.url):
                self._set_detected_app(webpage.url, tech_fingerprint, 'url', pattern, value=webpage.url)
        # analyze headers patterns
        for name, patterns in list(tech_fingerprint.headers.items()):
            if name in webpage.headers:
                content = webpage.headers[name]
                for pattern in patterns:
                    if pattern.regex.search(content):
                        self._set_detected_app(webpage.url, tech_fingerprint, 'headers', pattern, value=content,
                                               key=name)
                        has_tech = True
        # analyze scripts src patterns
        for pattern in tech_fingerprint.scriptSrc:
            for script in webpage.scripts:
                if pattern.regex.search(script):
                    self._set_detected_app(webpage.url, tech_fingerprint, 'scriptSrc', pattern, value=script)
                    has_tech = True
        # analyze meta patterns
        for name, patterns in list(tech_fingerprint.meta.items()):
            if name in webpage.meta:
                content = webpage.meta[name]
                for pattern in patterns:
                    if pattern.regex.search(content):
                        self._set_detected_app(webpage.url, tech_fingerprint, 'meta', pattern, value=content, key=name)
                        has_tech = True
        # analyze html patterns
        for pattern in tech_fingerprint.html:
            if pattern.regex.search(webpage.html):
                self._set_detected_app(webpage.url, tech_fingerprint, 'html', pattern, value=webpage.html)
                has_tech = True
        # analyze dom patterns
        # css selector, list of css selectors, or dict from css selector to dict with some of keys:
        #           - "exists": "": only check if the selector matches somthing, equivalent to the list form.
        #           - "text": "regex": check if the .innerText property of the element that matches the css selector matches the regex (with version extraction).
        #           - "attributes": {dict from attr name to regex}: check if the attribute value of the element that matches the css selector matches the regex (with version extraction).
        for selector in tech_fingerprint.dom:
            for item in webpage.select(selector.selector):
                if selector.exists:
                    self._set_detected_app(webpage.url, tech_fingerprint, 'dom', Pattern(string=selector.selector),
                                           value='')
                    has_tech = True
                if selector.text:
                    for pattern in selector.text:
                        if pattern.regex.search(item.inner_html):
                            self._set_detected_app(webpage.url, tech_fingerprint, 'dom', pattern, value=item.inner_html)
                            has_tech = True
                if selector.attributes:
                    for attrname, patterns in list(selector.attributes.items()):
                        _content = item.attributes.get(attrname)
                        if isinstance(_content, str) or type(_content) == int:
                            for pattern in patterns:
                                if pattern.regex.search(_content):
                                    self._set_detected_app(webpage.url, tech_fingerprint, 'dom', pattern,
                                                           value=_content)
                                    has_tech = True
        return has_tech

    def _set_detected_app(self, url: str,
                          tech_fingerprint: Fingerprint,
                          app_type: str,
                          pattern: Pattern,
                          value: str,
                          key='') -> None:
        # Lookup Technology object in the cache
        if url not in self.detected_technologies:
            self.detected_technologies[url] = {}
        if tech_fingerprint.name not in self.detected_technologies[url]:
            self.detected_technologies[url][tech_fingerprint.name] = Technology(tech_fingerprint.name)
        detected_tech = self.detected_technologies[url][tech_fingerprint.name]

        # Set confidence level
        if key != '': key += ' '
        match_name = app_type + ' ' + key + pattern.string

        detected_tech.confidence[match_name] = pattern.confidence

        # Dectect version number
        if pattern.version:
            allmatches = re.findall(pattern.regex, value)
            for i, matches in enumerate(allmatches):
                version = pattern.version
                # Check for a string to avoid enumerating the string
                if isinstance(matches, str):
                    matches = [(matches)]
                for index, match in enumerate(matches):
                    # Parse ternary operator
                    ternary = re.search(re.compile('\\\\' + str(index + 1) + '\\?([^:]+):(.*)$', re.I), version)
                    if ternary and len(ternary.groups()) == 2 and ternary.group(1) is not None and ternary.group(
                            2) is not None:
                        version = version.replace(ternary.group(0), ternary.group(1) if match != ''
                        else ternary.group(2))
                    # Replace back references
                    version = version.replace('\\' + str(index + 1), match)
                if version != '' and version not in detected_tech.versions:
                    detected_tech.versions.append(version)
            self._sort_app_version(detected_tech)

    def _sort_app_version(self, detected_tech: Technology) -> None:
        if len(detected_tech.versions) >= 1:
            return
        detected_tech.versions = sorted(detected_tech.versions, key=self._cmp_to_key(self._sort_app_versions))

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

    def get_categories(self, tech_name: str) -> List[str]:
        cat_nums = self.technologies[tech_name].cats if tech_name in self.technologies else []
        cat_names = [self.categories[str(cat_num)].name
                     for cat_num in cat_nums if str(cat_num) in self.categories]
        return cat_names

    def get_versions(self, url: str, app_name: str) -> List[str]:
        try:
            return self.detected_technologies[url][app_name].versions
        except KeyError:
            return []

    def get_confidence(self, url: str, app_name: str) -> Optional[int]:
        try:
            return self.detected_technologies[url][app_name].confidenceTotal
        except KeyError:
            return None

    def analyze(self, webpage: IWebPage) -> Set[str]:
        detected_technologies = set()

        for tech_name, technology in list(self.technologies.items()):
            if self._has_technology(technology, webpage):
                detected_technologies.add(tech_name)
        detected_technologies.update(self._get_implied_technologies(detected_technologies))

        return detected_technologies

    def analyze_with_versions(self, webpage: IWebPage) -> Dict[str, Dict[str, Any]]:
        detected_apps = self.analyze(webpage)
        versioned_apps = {}

        for app_name in detected_apps:
            versions = self.get_versions(webpage.url, app_name)
            versioned_apps[app_name] = {"versions": versions}

        return versioned_apps

    def analyze_with_categories(self, webpage: IWebPage) -> Dict[str, Dict[str, Any]]:
        detected_technologies = self.analyze(webpage)
        categorised_technologies = {}

        for tech_name in detected_technologies:
            cat_names = self.get_categories(tech_name)
            categorised_technologies[tech_name] = {"categories": cat_names}

        return categorised_technologies

    def analyze_with_versions_and_categories(self, webpage: IWebPage) -> Dict[str, Dict[str, Any]]:
        versioned_apps = self.analyze_with_versions(webpage)
        versioned_and_categorised_apps = versioned_apps

        for app_name in versioned_apps:
            cat_names = self.get_categories(app_name)
            versioned_and_categorised_apps[app_name]["categories"] = cat_names

        return versioned_and_categorised_apps

    def _sort_app_versions(self, version_a: str, version_b: str) -> int:
        return len(version_a) - len(version_b)

    def _cmp_to_key(self, mycmp: Callable[..., Any]):
        # https://docs.python.org/3/howto/sorting.html
        class CmpToKey:
            def __init__(self, obj, *args):
                self.obj = obj

            def __lt__(self, other):
                return mycmp(self.obj, other.obj) < 0

            def __gt__(self, other):
                return mycmp(self.obj, other.obj) > 0

            def __eq__(self, other):
                return mycmp(self.obj, other.obj) == 0

            def __le__(self, other):
                return mycmp(self.obj, other.obj) <= 0

            def __ge__(self, other):
                return mycmp(self.obj, other.obj) >= 0

            def __ne__(self, other):
                return mycmp(self.obj, other.obj) != 0

        return CmpToKey