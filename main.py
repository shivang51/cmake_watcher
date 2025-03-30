import os
import time
import argparse
from watchdog.observers import Observer
from src.cmake_watcher import CMakeWatcher
from src.file_event_handler import FileEventHandler

def main():
    parser = argparse.ArgumentParser(
        description="File watcher and CMake updater. Parses CMake files for variables preceded by '#!CMAKE_WATCHER_OBSERVE' and updates them when watched files change."
    )
    parser.add_argument("cmake_file", help="Path to the main CMake file (usually CMakeLists.txt)")
    args = parser.parse_args()

    cmake_watcher = CMakeWatcher(args.cmake_file)
    cmake_watcher.parse()

    # Backup all CMakeLists.txt files before starting the watcher.
    cmake_watcher.backup_files()

    # Determine watch directories from the observed variables.
    watch_dirs = cmake_watcher.get_watch_directories()
    if not watch_dirs:
        fallback = os.path.dirname(os.path.abspath(args.cmake_file))
        print(f"No valid watch directories found in CMake variables. Falling back to: {fallback}")
        watch_dirs = [fallback]
    else:
        print("Watch directories found from CMake variables:")
        for wd in watch_dirs:
            print(" ", wd)

    event_handler = FileEventHandler(cmake_watcher)
    observer = Observer()
    for directory in watch_dirs:
        observer.schedule(event_handler, directory, recursive=True)
    observer.start()
    print("Started watching directories:")
    for d in watch_dirs:
        print(" ", d)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping file watcher.")
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()

