


frontend_path = 'frontend/frontend-full-v2/my-app'
file_list = [
  ('backend/langgraph_server-v2/server.py', 'the fastapi backend server'),
  ('backend/langgraph_server-v2/thread_manager.py','the model of thread metadata.'),
  (f'{frontend_path}/components/assistant-ui/threadlist-sidebar.tsx', 'the threadlist sidebar component'),
  (f'{frontend_path}/components/assistant-ui/thread.tsx', 'the thread component '),
  (f'{frontend_path}/components/assistant-ui/thread-list.tsx' , 'thread list component'),
  (f'{frontend_path}/components/assistant-ui/share-button.tsx','the share button impl'),
  (f'{frontend_path}/app/langchainToAui.tsx','the share button impl'),
  (f'{frontend_path}/app/assistant.tsx', 'the assistant.tsx file (containing most of the main page elements)'),
  (f'{frontend_path}/app/MyRuntimeProvider.tsx', 'the runtime provider'),
  (f'{frontend_path}/app/MyMessageConverter.tsx', 'contains the converter implementation'),
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


s = '# Source code:\n'
for fpath, fdesc in file_list:
  s += _paste_file(fpath, fdesc)

print(s)
