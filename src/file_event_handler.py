import os
from watchdog.events import FileSystemEventHandler

class FileEventHandler(FileSystemEventHandler):
    def __init__(self, cmake_watcher):
        self.cmake_watcher = cmake_watcher

    def on_created(self, event):
        if event.is_directory:
            return
        self.handle_event(event, event_type="created")

    def on_modified(self, event):
        if event.is_directory:
            return
        self.handle_event(event, event_type="modified")

    def on_deleted(self, event):
        if event.is_directory:
            return
        self.handle_event(event, event_type="deleted")

    def on_moved(self, event):
        if event.is_directory:
            return
        self.handle_event(event, event_type="moved", new_path=event.dest_path)

    def handle_event(self, event, event_type, new_path=None):
        file_path = os.path.abspath(event.src_path)
        if event_type == "moved":
            new_value = os.path.abspath(str(new_path))
            print(f"File event: moved for '{file_path}'. Updating variable with new value '{new_value}'")
            self.cmake_watcher.update_variable_by_file_event(event_type, file_path, new_value)
        else:
            print(f"File event: {event_type} for '{file_path}'. Updating variable.")
            self.cmake_watcher.update_variable_by_file_event(event_type, file_path)


