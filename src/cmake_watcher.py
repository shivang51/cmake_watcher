import os
import re
import shutil
import shlex  # for splitting while preserving quoted tokens

class CMakeWatcher:
    SPECIAL_MARKER = "#!CMAKE_WATCHER_OBSERVE"

    def __init__(self, main_cmake):
        self.main_cmake = os.path.abspath(main_cmake)
        # Maps CMake file paths to list of observed variables.
        # Each tuple: (var_name, var_value, start_line, command_block, indent)
        self.results = {}
        # Cache file content as a list of lines to avoid repeated disk reads.
        self.file_cache = {}
        # Track modification times of the CMake files.
        self.mod_times = {}
        self.visited = set()

    def parse(self):
        self._parse_recursive(self.main_cmake)

    def _parse_recursive(self, file_path):
        file_path = os.path.abspath(file_path)
        if file_path in self.visited:
            return
        self.visited.add(file_path)
        try:
            observed_vars = self._parse_observed_variables(file_path)
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return
        self.results[file_path] = observed_vars
        with open(file_path, 'r') as f:
            self.file_cache[file_path] = f.readlines()
        self.mod_times[file_path] = os.path.getmtime(file_path)
        subdirs = self._parse_add_subdirectory(file_path)
        base_dir = os.path.dirname(file_path)
        for sub in subdirs:
            sub_dir = os.path.join(base_dir, sub)
            sub_cmake = os.path.join(sub_dir, 'CMakeLists.txt')
            if os.path.exists(sub_cmake):
                self._parse_recursive(sub_cmake)

    def _parse_observed_variables(self, file_path):
        with open(file_path, 'r') as f:
            lines = f.readlines()
        observed_vars = []
        i = 0
        marker_found = False
        total_lines = len(lines)
        while i < total_lines:
            line = lines[i]
            if self.SPECIAL_MARKER in line:
                marker_found = True
                i += 1
                continue
            m = re.search(r'^(\s*)set\s*\(', line, re.IGNORECASE)
            if m:
                indent = m.group(1)
                start_line = i + 1  # human-readable line number
                command_block = line.rstrip("\n")
                paren_count = line.count('(') - line.count(')')
                i += 1
                while paren_count > 0 and i < total_lines:
                    command_block += "\n" + lines[i].rstrip("\n")
                    paren_count += lines[i].count('(') - lines[i].count(')')
                    i += 1
                if marker_found:
                    try:
                        inner = command_block.split("(", 1)[1].rsplit(")", 1)[0].strip()
                        tokens = inner.split()
                        if tokens:
                            var_name = tokens[0]
                            var_value = " ".join(tokens[1:]) if len(tokens) > 1 else ""
                            observed_vars.append((var_name, var_value, start_line, command_block, indent))
                    except Exception:
                        pass
                    marker_found = False
                continue
            i += 1
        return observed_vars

    def _parse_add_subdirectory(self, file_path):
        with open(file_path, 'r') as f:
            lines = f.readlines()
        subdirs = []
        i = 0
        total_lines = len(lines)
        while i < total_lines:
            line = lines[i]
            m = re.search(r'\badd_subdirectory\s*\(', line, re.IGNORECASE)
            if m:
                command_block = line.rstrip("\n")
                paren_count = line.count('(') - line.count(')')
                i += 1
                while paren_count > 0 and i < total_lines:
                    command_block += " " + lines[i].strip()
                    paren_count += lines[i].count('(') - lines[i].count(')')
                    i += 1
                try:
                    inner = command_block.split("(", 1)[1].rsplit(")", 1)[0].strip()
                    parts = inner.split()
                    if parts:
                        subdirs.append(parts[0])
                except Exception:
                    pass
            else:
                i += 1
        return subdirs

    def update_variable_by_file_event(self, event_type, file_path, new_file_path=None):
        """
        For each observed variable in the parsed CMake files, if the event file's directory matches
        the directory of any file in the variable's file list, update that variable.
        For created/modified events, add file_path if not present.
        For deleted events, remove file_path if present.
        For moved events, replace file_path with new_file_path.
        """
        import shlex
        updated_any = False
        norm_event = os.path.normpath(file_path)
        event_dir = os.path.dirname(norm_event)
        for cmake_file, var_list in self.results.items():
            base_dir = os.path.dirname(cmake_file)
            for variable, var_value, start_line, command_block, indent in var_list:
                # Get file tokens from the variable value.
                try:
                    tokens = shlex.split(var_value)
                except Exception:
                    tokens = var_value.split()
                # Resolve tokens relative to the directory of the CMake file.
                file_paths = [os.path.normpath(os.path.join(base_dir, token.strip('"'))) for token in tokens]
                # Check if any file in the variable's list is from the same directory as the event.
                match = any(os.path.dirname(fp) == event_dir for fp in file_paths)
                if match:
                    res = self.update_variable(variable, event_type, file_path, new_file_path)
                    if res:
                        updated_any = True
        return updated_any

    def update_variable(self, variable, event_type, file_path, new_file_path=None):
        """
        Update all occurrences of the given variable in the cached CMake files based on the event type.
          - For "created" or "modified": add file_path (relative to the CMakeLists.txt location) if not present.
          - For "deleted": remove file_path (relative) if present.
          - For "moved": replace file_path with new_file_path (both relative) if applicable.
        """
        modified_any = False

        for cmake_file, vars_list in self.results.items():
            # Check if the file was changed externally; if so, reload its content.
            try:
                current_mod = os.path.getmtime(cmake_file)
            except Exception:
                continue
            if current_mod > self.mod_times.get(cmake_file, 0):
                with open(cmake_file, 'r') as f:
                    self.file_cache[cmake_file] = f.readlines()
                self.mod_times[cmake_file] = current_mod

            base_dir = os.path.dirname(cmake_file)
            lines = self.file_cache[cmake_file]
            modified = False
            i = 0
            new_lines = []
            total_lines = len(lines)
            while i < total_lines:
                line = lines[i]
                if self.SPECIAL_MARKER in line:
                    new_lines.append(line)
                    i += 1
                    if i < total_lines:
                        m = re.search(r'^(\s*)set\s*\(', lines[i], re.IGNORECASE)
                        if m:
                            indent = m.group(1)
                            command_block = lines[i].rstrip("\n")
                            paren_count = lines[i].count('(') - lines[i].count(')')
                            i += 1
                            while paren_count > 0 and i < total_lines:
                                command_block += "\n" + lines[i].rstrip("\n")
                                paren_count += lines[i].count('(') - lines[i].count(')')
                                i += 1
                            try:
                                inner = command_block.split("(", 1)[1].rsplit(")", 1)[0].strip()
                                tokens = shlex.split(inner)
                                if tokens and tokens[0] == variable:
                                    # Compute current file tokens (assumed to be relative) and normalize them.
                                    current_files = [os.path.normpath(token.strip('"')) for token in tokens[1:]]
                                    updated_files = current_files.copy()
                                    # Compute relative paths for the event file.
                                    rel_event = os.path.normpath(os.path.relpath(file_path, base_dir))
                                    rel_new = os.path.normpath(os.path.relpath(new_file_path, base_dir)) if new_file_path else None

                                    if event_type in ("created", "modified"):
                                        if rel_event not in current_files:
                                            updated_files.append(rel_event)
                                            modified = True
                                    elif event_type == "deleted":
                                        if rel_event in current_files:
                                            updated_files = [f for f in current_files if f != rel_event]
                                            modified = True
                                    elif event_type == "moved":
                                        if rel_event in current_files:
                                            updated_files = [rel_new if f == rel_event else f for f in current_files]
                                            modified = True
                                        else:
                                            if rel_new not in current_files:
                                                updated_files.append(str(rel_new))
                                                modified = True

                                    # Rebuild the set() command with one file per line.
                                    new_cmd = f"{indent}set({variable}\n" + "\n".join(f'"{f}"' for f in updated_files) + "\n)\n"
                                    new_lines.append(new_cmd)
                                else:
                                    new_lines.append(command_block + "\n")
                            except Exception:
                                new_lines.append(command_block + "\n")
                        else:
                            continue
                else:
                    new_lines.append(line)
                    i += 1
            if modified:
                with open(cmake_file, 'w') as f:
                    f.writelines(new_lines)
                self.file_cache[cmake_file] = new_lines
                print(f"Modified variable '{variable}' in {cmake_file}")
                modified_any = True
        return modified_any


    def get_watch_directories(self):
        """Return a list of valid directories to watch.
           Each variable’s value is interpreted as file path(s) relative to the CMake file in which it is defined.
           The variable may contain multiple file paths enclosed in double quotes.
           Since these paths refer to files, their directory names are used.
           The most low-level common directory among all is returned if possible."""
        all_dirs = []
        for file_path, var_list in self.results.items():
            base_dir = os.path.dirname(file_path)
            for var_name, var_value, _, _, _ in var_list:
                if not var_value:
                    continue
                # Extract file paths from var_value (may be multiple, in double quotes).
                paths = re.findall(r'"([^"]+)"', var_value)
                if not paths:
                    paths = [var_value]
                for p in paths:
                    resolved = os.path.join(base_dir, p) if not os.path.isabs(p) else p
                    resolved = os.path.normpath(resolved)
                    # Use the directory name of the file path.
                    dir_path = os.path.dirname(resolved)
                    if os.path.isdir(dir_path):
                        all_dirs.append(dir_path)
        if not all_dirs:
            return []
        common_dir = os.path.commonpath(all_dirs)
        if os.path.isdir(common_dir):
            return [common_dir]
        else:
            return list(set(all_dirs))

    def backup_files(self):
        """
        Backup all CMakeLists.txt files found in the parsed tree.
        The backup folder (.cmake_observer_backup) will be created in the directory of the main CMake file,
        preserving the folder structure relative to that directory.
        """
        backup_root = os.path.join(os.path.dirname(self.main_cmake), ".cmake_observer_backup")
        for file_path in self.results.keys():
            # Compute relative path from the main CMake file's directory.
            rel_path = os.path.relpath(file_path, os.path.dirname(self.main_cmake))
            backup_path = os.path.join(backup_root, rel_path)
            backup_dir = os.path.dirname(backup_path)
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            shutil.copy2(file_path, backup_path)
            print(f"Backed up {file_path} to {backup_path}")

