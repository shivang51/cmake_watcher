# CMake Observer & Updater

This tool monitors directories referenced in your CMake files and automatically updates specific CMake variables when files are created, deleted, modified, or moved.

## What It Does

- **Parses CMake Files:**  
  It scans your main CMakeLists.txt (and any files included via `add_subdirectory`) for variables defined with a `set()` command that are immediately preceded by a marker comment (`#!CMAKE_WATCHER_OBSERVE`).

- **Monitors File Changes:**  
  It automatically watches directories determined from the file paths listed in those variables. When a file event occurs in one of these directories, the tool:
  - **Adds** a new file’s relative path if it’s created or modified.
  - **Removes** a file’s path if it is deleted.
  - **Replaces** the old path with a new one if the file is renamed or moved.

- **Maintains Relative Paths:**  
  The file paths stored in the CMake variables remain relative to the CMake file’s location.

- **Backs Up CMake Files:**  
  Before making any changes, all parsed CMakeLists.txt files are backed up in a folder named `.cmake_observer_backup`, preserving their folder structure.

- **Handles External Modifications:**  
  If a CMake file is modified externally, the tool refreshes its cache so updates are always applied to the latest version.

## How to Use

1. **Install Dependencies:**

   Install the required packages by running:
   ```sh
   pip install -r requirements.txt

2. **Run the Tool:**

	Start the tool by executing:
	```sh
	python main.py /path/to/CMakeLists.txt
    ```
	Replace `/path/to/CMakeLists.txt` with the path to your main CMake file.

3. Watch for Updates:
	The tool will monitor the directories and update the appropriate variables in your CMake files automatically based on file events.

## Required Changes in Your CMakeLists.txt

- **Add the Marker Comment:**  
  Immediately before any `set()` command you want the tool to update, insert:
	```sh
	#!CMAKE_WATCHER_OBSERVE

- **Define Variables with Relative Paths:**  
	Ensure that the variable is defined with file paths (enclosed in double quotes) relative to the CMakeLists.txt file. For example:
	```cmake
	#!CMAKE_WATCHER_OBSERVE
	set(Header_Files
		"path/to/file1"
		"path/to/file2"
	)

The tool will update this list by adding, removing, or replacing file paths based on file events in the corresponding directory.
