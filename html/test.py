import os
import json
print('<pre>')
print(json.dumps(dict(os.environ), indent=4).replace('\n', '<br>').replace(' ', '&nbsp;'))
print('</pre>')
