import core.errors as errors
import numpy as np
import librosa
import os
from dataclasses import dataclass
from typing import Callable, Optional

logger = errors.logger_config.LoggerSingleton().get_logger()


@dataclass
class AudioFile:
    path: str
    name: str
    audio_signal_unloaded: Callable[[], np.ndarray]
    sample_rate: int

    @property
    def audio_signal_loaded(self) -> np.ndarray:
        return self.audio_signal_unloaded()

    def check_audio(self, configuration_path: str) -> bool:
        verifications = [
            (errors.check_audio_corruption, (self.path + self.name,), {},
             f"Audio file '{self.path}' is corrupted"),
            (errors.check_audio_format, (),
             {'path': self.path, 'name': self.name, 'configuration_path': configuration_path},
             f"Invalid file format for '{self.name}'"),
            (errors.check_path_accessible, (self.path,), {},
             f"Path '{self.path}' does not exist or is not accessible"),
            (errors.check_path_accessible, (configuration_path,), {},
             f"Path '{configuration_path}' does not exist or is not accessible")
        ]

        no_error = all(
            logger.error(error_message.format(audio_data=self))
            if not check_function(*args, **kwargs)
            else True
            for check_function, args, kwargs, error_message in verifications
        )

        return no_error


class WorkingSet:
    name: str

    def __init__(self, name: str, /, *, test_mode: bool = False, data_set: dict = None):
        self.name = name

        if not test_mode:
            self.working_set = {"individual_files":  []}
        else:
            self.working_set = data_set

    def __getitem__(self, name: str, group: str = "individual_files", /) -> Optional[AudioFile]:
        if group not in self.working_set:
            logger.error(f"No group with name '{group}' was found in working set '{self.name}'")
            return None

        for file in self.working_set[group]:
            if file.name == name:
                return file
        logger.error(f"No file with name '{name}' was found in key '{group}' in working set '{self.name}'")
        return None

    def __contains__(self, *, name: str, group: str = "individual_files") -> bool:
        if (group not in self.working_set or
                name not in [audio.name for audio in self.working_set[group]]):
            return False
        return True

    def add_file(self, *, path: str, name: str, configuration_path: str, group: str = "individual_files") -> bool:
        if not errors.validate_path(path=path, name=name):
            logger.error(f"Path '{path + name}' does not exist or is not accessible")
            return False

        audio_signal, sample_rate = librosa.load(os.path.join(path, name))
        audio = AudioFile(path=path, name=name,
                          audio_signal_unloaded=lambda: audio_signal, sample_rate=int(sample_rate))

        if not audio.check_audio(configuration_path):
            logger.error(f"Could not add file '{name}' in group '{group}' in working set '{self.name}'")
            return False
        if group == "":
            logger.error("Can not add groups with empty names")
            return False

        if group in self.working_set:
            self.working_set[group].append(audio)
        else:
            self.working_set[group] = [audio]
        return True

    def remove_file(self, *, name: str, group: str = "individual_files") -> bool:
        if group not in self.working_set or not any(audio.name == name for audio in self.working_set[group]):
            logger.error(f"Could not delete file. "
                         f"No file with name '{name}' was found in key '{group}' in working set '{self.name}'")
            return False
        else:
            self.working_set[group] = [audio for audio in self.working_set[group] if audio.name != name]
            return True

    def add_directory(self, *, path: str, configuration_path: str, group: str = "individual_files") -> bool:
        any_files_added = False

        directory_verifications = [
            (errors.check_path_accessible, (path,),
             f"Path '{path}' does not exist or is not accessible"),
            (errors.check_path_accessible, (configuration_path,),
             f"Path '{configuration_path}' does not exist or is not accessible"),
            (lambda check_group: group != "", (group,), "Can not add groups with empty names")
        ]

        no_error = all(
            logger.error(error_message.format(audio_data=self))
            if not check_function(*args)
            else True
            for check_function, args, error_message in directory_verifications
        )

        if not no_error:
            return False

        for file_name in os.listdir(path):
            if os.path.isfile(os.path.join(path, file_name)):
                if self.add_file(path=path, name=file_name, configuration_path=configuration_path, group=group):
                    any_files_added = True

        return any_files_added
