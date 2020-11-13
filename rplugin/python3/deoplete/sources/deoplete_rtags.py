import re
import json
from pprint import pprint
from subprocess import Popen, PIPE, TimeoutExpired

from deoplete.source.base import Base

current = __file__


class Source(Base):
    def __init__(self, vim):
        Base.__init__(self, vim)
        self.name = 'rtags'
        self.mark = '[rtags]'
        self.filetypes = ['c', 'cpp', 'objc', 'objcpp']
        self.rank = 500
        self.is_bytepos = True
        self.min_pattern_length = 1
        self.input_pattern = (r'[^. \t0-9]\.\w*|'
                              r'[^. \t0-9]->\w*|'
                              r'[a-zA-Z_]\w*::\w*')
        self._retry_count = 0

    def get_complete_position(self, context):
        m = re.search(r'\w*$', context['input'])
        return m.start() if m else -1

    def gather_candidates(self, context):
        line = context['position'][1]
        col = (context['complete_position'] + 1)

        buf = self.vim.current.buffer
        buf_name = buf.name
        buf = buf[0:line]
        buf[-1] = buf[-1][0:col]
        text = "\n".join(buf)

        word = context['complete_str']

        context['is_async'] = False

        vars = self.vim.vars
        timeout = vars.get('deoplete#source#rtags#timeout', None)
        retry_count = vars.get('deoplete#source#rtags#retry', 10)

        if context['is_refresh']:
            self._retry_count = 0

        command = self.get_rc_command(buf_name, line, col, len(text), word, timeout)
        rc = None
        try:
            p = Popen(command, stdout=PIPE, stdin=PIPE, stderr=PIPE, close_fds = True)
            stdout_data, stderr_data = p.communicate(input=text.encode("utf-8"))
            rc = p.returncode
        except:
            return []

        if p.returncode != 0:
            if p.returncode == 34: # rc timeout
                self._retry_count += 1
                if self._retry_count < retry_count:
                    context['is_async'] = True
            return []

        if not stdout_data:
            return []

        self._retry_count = 0

        stdout_data_decoded = stdout_data.decode("utf-8", 'ignore')  
        completions = []
        for line in stdout_data_decoded.splitlines():
            completion = {'dup': 1}
            line = line.rsplit(None, 1)[0]
            completion['word'], completion['menu'], *_ = line.split(None, 1) + [None, None]
            completions.append(completion) 
        return completions

    def get_rc_command(self, file_name, line, column, offset, word, timeout):
        command = ["rc", "--absolute-path", "--synchronous-completions"]
        if (timeout):
            command.append("--timeout={}".format(timeout))
        command += ["-l", "{}:{}:{}".format(file_name, line, column)]
        if (word):
            command.append("--code-complete-prefix={}".format(word))
        command.append("--unsaved-file={}:{}".format(file_name, offset))
        return command
