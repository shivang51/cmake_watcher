import unittest
import tempfile
import os
import shutil
from cmake_watcher import CMakeWatcher

class TestCMakeWatcher(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing.
        self.test_dir = tempfile.mkdtemp()
        # Create a main CMake file with sample content.
        self.main_cmake = os.path.join(self.test_dir, "CMakeLists.txt")
        self.initial_content = '''#!CMAKE_WATCHER_OBSERVE
set(Header_Files
"path/to/a"
"path/to/b"
)
'''
        with open(self.main_cmake, "w") as f:
            f.write(self.initial_content)
        # Instantiate and parse.
        self.watcher = CMakeWatcher(self.main_cmake)
        self.watcher.parse()

    def tearDown(self):
        # Clean up the temporary directory.
        shutil.rmtree(self.test_dir)

    def test_initial_parse(self):
        # Confirm that the main CMake file was parsed and the variable is present.
        self.assertIn(self.main_cmake, self.watcher.results)
        results = self.watcher.results[self.main_cmake]
        self.assertEqual(len(results), 1)
        variable, var_value, start_line, command_block, indent = results[0]
        self.assertEqual(variable, "Header_Files")
        # Check that both paths are present.
        self.assertIn("path/to/a", var_value)
        self.assertIn("path/to/b", var_value)

    def test_create_event(self):
        # Simulate creation of a new file that should be added.
        # Create a file at <test_dir>/path/to/c.
        file_path = os.path.join(self.test_dir, "path/to/c")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            f.write("dummy content")
        # Call update_variable() for a "created" event.
        self.watcher.update_variable("Header_Files", "created", file_path)
        # Read back the main CMake file.
        with open(self.main_cmake, "r") as f:
            content = f.read()
        # Expect the relative path "path/to/c" to be added.
        self.assertIn('"path/to/c"', content)
        # Ensure existing entries are still present.
        self.assertIn('"path/to/a"', content)
        self.assertIn('"path/to/b"', content)

    def test_deleted_event(self):
        # Simulate deletion of the file corresponding to "path/to/b".
        file_path = os.path.join(self.test_dir, "path/to/b")
        # Call update_variable() for a "deleted" event.
        self.watcher.update_variable("Header_Files", "deleted", file_path)
        with open(self.main_cmake, "r") as f:
            content = f.read()
        # "path/to/b" should be removed.
        self.assertNotIn('"path/to/b"', content)
        # "path/to/a" should remain.
        self.assertIn('"path/to/a"', content)

    def test_moved_event(self):
        # Simulate a file move from "path/to/b" to "path/to/x".
        old_file_path = os.path.join(self.test_dir, "path/to/b")
        new_file_path = os.path.join(self.test_dir, "path/to/x")
        # Call update_variable() for a "moved" event.
        self.watcher.update_variable("Header_Files", "moved", old_file_path, new_file_path)
        with open(self.main_cmake, "r") as f:
            content = f.read()
        # "path/to/b" should be replaced by "path/to/x".
        self.assertNotIn('"path/to/b"', content)
        self.assertIn('"path/to/x"', content)
        self.assertIn('"path/to/a"', content)

    def test_external_modification(self):
        # Simulate an external change by rewriting the main CMake file.
        external_content = '''#!CMAKE_WATCHER_OBSERVE
set(Header_Files
"path/to/a"
"path/to/b"
"path/to/y"
)
'''
        with open(self.main_cmake, "w") as f:
            f.write(external_content)
        # Update the modification time.
        os.utime(self.main_cmake, None)
        # Now simulate a deletion event for "path/to/b".
        file_path = os.path.join(self.test_dir, "path/to/b")
        self.watcher.update_variable("Header_Files", "deleted", file_path)
        with open(self.main_cmake, "r") as f:
            content = f.read()
        # "path/to/b" should be removed; others remain.
        self.assertNotIn('"path/to/b"', content)
        self.assertIn('"path/to/a"', content)
        self.assertIn('"path/to/y"', content)

if __name__ == '__main__':
    unittest.main()

