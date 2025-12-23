


frontend_path = 'frontend/frontend-full/my-app'
file_list = [
  ('backend/langgraph_server-v2/server.py', 'the fastapi backend server'),
  (f'{frontend_path}/components/assistant-ui/threadlist-sidebar.tsx', 'the threadlist sidebar component'),
  (f'{frontend_path}/components/assistant-ui/thread-list.tsx' , 'thread list component'),
  (f'{frontend_path}/app/assistant.tsx', 'the assistant.tsx file (containing most of the main page elements)'),
  (f'{frontend_path}/app/MyRuntimeProvider.tsx', 'the runtime provider')
]

from pathlib import Path
def _paste_file(fpath, fdesc):
  fname = fpath.split('/')[-1]
  fpreamble = fname  + ': ('+fdesc+')'
  fpreamble += '\n' + len(fpreamble)*'-'
  s = fpreamble
  with open(fpath, 'r') as f:
    s += f.read()
  return s + '\n' + '---' +'\n'


s = ''
for fpath, fdesc in file_list:
  s += _paste_file(fpath, fdesc)

print(s)
