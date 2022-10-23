import os
import json
import pathlib
from typing import List
from .store_data import StoreData
from datetime import datetime, timedelta


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
        should_update = True
        _technologies_file: pathlib.Path
        _files = self.__find_files(['PWD'], ['./technologies.json'])
        if _files:
            _technologies_file = pathlib.Path(_files[0])
            last_modification_time = datetime.fromtimestamp(_technologies_file.stat().st_mtime)
            if datetime.now() - last_modification_time < timedelta(hours=24):
                should_update = False

        # Get the lastest file
        if should_update or force_update:
            try:
                obj = StoreData().get_latest_tech_data()
                _technologies_file = pathlib.Path(self.__find_files(
                    ['PWD'],
                    ['./technologies.json'],
                    create=True
                ).pop())

                with _technologies_file.open('w', encoding='utf-8') as tfile:
                    tfile.write(json.dumps(obj))

            except Exception as err:  # Or loads default
                obj = None
        else:
            with _technologies_file.open('r', encoding='utf-8') as tfile:
                obj = json.load(tfile)
        return obj

    def __find_files(
            self,
            env_location: List[str],
            potential_files: List[str],
            default_content: str = "",
            create: bool = False,
    ) -> List[str]:
        """Find existent files based on folders name and file names.
        Arguments:
        - `env_location`: list of environment variable to use as a base path. Exemple: ['HOME', 'XDG_CONFIG_HOME', 'APPDATA', 'PWD']
        - `potential_files`: list of filenames. Exemple: ['.myapp/conf.ini',]
        - `default_content`: Write default content if the file does not exist
        - `create`: Create the file in the first existing env_location with default content if the file does not exist
        """
        potential_paths = []
        existent_files = []

        env_loc_exists = False
        # build potential_paths of config file
        for env_var in env_location:
            if env_var in os.environ:
                env_loc_exists = True
                for file_path in potential_files:
                    potential_paths.append(os.path.join(os.environ[env_var], file_path))
        if not env_loc_exists and create:
            raise RuntimeError(f"Cannot find any of the env locations {env_location}. ")
        # If file exist, add to list
        for p in potential_paths:
            if os.path.isfile(p):
                existent_files.append(p)
        # If no file foud and create=True, init new file
        if len(existent_files) == 0 and create:
            os.makedirs(os.path.dirname(potential_paths[0]), exist_ok=True)
            with open(potential_paths[0], "w", encoding='utf-8') as config_file:
                config_file.write(default_content)
            existent_files.append(potential_paths[0])
        return existent_files
