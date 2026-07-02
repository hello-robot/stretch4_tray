"""Attempts to display a shell and execute a command on it to the user."""

from dataclasses import dataclass
import logging
import subprocess
import shlex

@dataclass
class ExecutionResult:
    success: bool
    returncode: int
    stdout: str
    stderr: str
    command: str
    pid: int

class VisibleShell:
    """A visible system shell for user interaction."""

    def __init__(self, shell_path: str = '/bin/bash'):
        self.shell_path = shell_path
        self.process = None

    def execute_command(self, command: str, cwd: str|None, process_logger:logging.Logger) -> ExecutionResult:
        """Execute a command in a visible terminal."""
        try:
            # Use gnome-terminal or xterm to open a visible shell
            terminal_cmd = self._get_terminal_command(command, cwd)

            if not terminal_cmd:
                raise Exception("No suitable terminal emulator found")
            
            process_logger.info(f"Executing command in visible terminal: {terminal_cmd}")

            # Start the terminal process
            self.process = subprocess.Popen(
                terminal_cmd,
                # stdout=subprocess.PIPE,
                # stderr=subprocess.PIPE,
                # shell=False,
                # text=True
            )

            return ExecutionResult(
                success=True,
                returncode=0,
                stdout=f"Command executed in visible terminal: {command}",
                stderr='',
                command=command,
                pid=self.process.pid
                )

        except Exception as e:
            process_logger.error(f"Error executing command in visible terminal: {e}")
            return ExecutionResult(
                success=False,
                returncode=1,
                stdout='',
                stderr=str(e),
                command=command,
                pid=-1
            )

    def _get_terminal_command(self, command: str, cwd: str|None = None) -> list[str]|None:
        """Get the appropriate terminal command for the system, also inject the command and a Press Enter to close... message at the end."""
        # Build the shell command
        quoted_command = shlex.quote(command)
        shell_cmd = f"echo '================='; echo ''; echo command: {quoted_command}; echo ''; echo '=================='; "
        if cwd:
            shell_cmd += f"cd {shlex.quote(cwd)} && {command}"
        else:
            shell_cmd += command

        # Add to history and keep open
        shell_cmd += f"; export HISTFILE=~/.bash_history; history -s {quoted_command}; history -a; exec bash"

        # Try different terminal emulators
        terminal_options = [
            ['gnome-terminal', '--', 'bash', '-c', shell_cmd],
            ['xterm', '-e', 'bash', '-c', shell_cmd],
            ['konsole', '-e', 'bash', '-c', shell_cmd],
            ['xfce4-terminal', '-e', f'bash -c "{shell_cmd}"'],
        ]

        for terminal_cmd in terminal_options:
            try:
                # Check if the terminal emulator exists
                result = subprocess.run(['which', terminal_cmd[0]],
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    return terminal_cmd
            except:
                continue

        return None

