import os
import json
import pathlib
from .store_data import StoreData


class GetData:

    def latest(self, force_update):
        """
        Construct a Wappalyzer instance.

        Use ``update=True`` to download the very latest file from internet.
        Do not update if the file has already been updated in the last 24 hours.
        *New in version 0.4.0*

        Use ``technologies_file=/some/path/technologies.json`` to load a
        custom technologies file.

        If no arguments is passed, load the default ``data/technologies.json`` file
        inside the package ressource.

        :param technologies_file: File path
        :param update: Download and use the latest ``technologies.json`` file
            from `AliasIO/wappalyzer <https://github.com/AliasIO/wappalyzer>`_ repository.

        """
        _technologies_file: pathlib.Path
        _file = os.path.join(pathlib.Path(__file__).resolve().parent, 'technologies.json')
        _technologies_file = pathlib.Path(_file)
        if force_update:
            try:
                obj = StoreData().get_latest_tech_data()
                with _technologies_file.open('w', encoding='utf-8') as tfile:
                    tfile.write(json.dumps(obj))

            except Exception as err:  # Or loads default
                obj = None
        else:
            with _technologies_file.open('r', encoding='utf-8') as tfile:
                obj = json.load(tfile)
        return obj